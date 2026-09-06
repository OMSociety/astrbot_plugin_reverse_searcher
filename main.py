import asyncio
import contextlib
import io
import os
import re
import tempfile
import time
from urllib.parse import urljoin

import httpx
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image as AstrImage
from astrbot.api.message_components import Reply
from astrbot.api.star import Context, Star
from PIL import Image

from .ReverseSearcher.engine_intro_pil import create_engine_intro_image
from .ReverseSearcher.engine_registry import ALL_ENGINES, ENGINE_REGISTRY
from .ReverseSearcher.message_extract import get_img_urls, get_message_text
from .ReverseSearcher.model import BaseSearchModel
from .ReverseSearcher.utils.security import (
    is_safe_image_url,
    is_safe_local_image_path,
)

# 渲染用引擎信息视图（从 ENGINE_REGISTRY 派生，仅本文件使用）
ENGINE_INFO = {
    name: {"url": def_.url, "anime": def_.anime_focused}
    for name, def_ in ENGINE_REGISTRY.items()
}


def is_image_url(text: str) -> bool:
    """
    判断文本是否为图片URL（https开头、常见图片扩展名结尾、公网主机）

    参数:
        text (str): 待检测文本

    返回:
        bool: 是安全的图片URL则True，否则False

    异常:
        无
    """
    if not re.match(r"^https://.*\.(jpg|jpeg|png|gif|webp|bmp)$", text, re.IGNORECASE):
        return False
    # SSRF 防护：拒绝内网/元数据地址
    return is_safe_image_url(text)


class ReverseSearcherPlugin(Star):
    """
    以图搜图插件主类

    实现图片及文本消息的识别、搜索入口流程控制与结果发送
    """

    def __init__(self, context: Context, config: dict):
        """
        初始化插件实例及配置

        参数:
            context: 机器人上下文对象
            config: 配置字典

        变量:
            client: HTTP异步客户端
            user_states: 用户状态字典
            cleanup_task: 用户超时定时清理协程
            available_engines: 实际启用的引擎列表
            search_params_timeout: 等待搜索参数的超时时间（秒）
            search_model: 搜索执行模型
            state_handlers: 状态处理器方法字典

        返回:
            无

        异常:
            无
        """
        super().__init__(context)
        # 下载图片走配置的代理（国内服务器访问 pixiv 等缩略图必需）
        self.client = httpx.AsyncClient(proxy=config.get("proxies", "") or None)
        self.user_states = {}
        self.cleanup_task = asyncio.create_task(self.cleanup_loop())
        available_apis_config = config.get("available_apis", {})
        self.available_engines = [
            e for e in ALL_ENGINES if available_apis_config.get(e, True)
        ]
        timeout_settings = config.get("timeout_settings", {})
        self.search_params_timeout = timeout_settings.get("search_params_timeout", 30)
        keyword_config = config.get("keyword", {})
        trigger_keywords = keyword_config.get("trigger_keywords", ["以图搜图"])
        # 确保触发关键词是列表格式，如果为空或无效则使用默认值
        if isinstance(trigger_keywords, list) and trigger_keywords:
            self.trigger_keywords = [
                kw.strip() for kw in trigger_keywords if kw and kw.strip()
            ]
        else:
            self.trigger_keywords = ["以图搜图"]
        self.enable_keyword_trigger = config.get("enable_keyword_trigger", True)
        engine_keywords_config = keyword_config.get("engine_keywords", {})
        self.engine_keywords = {}
        for engine in ALL_ENGINES:
            keyword = engine_keywords_config.get(engine)
            if keyword and keyword.strip():
                self.engine_keywords[keyword.strip().lower()] = engine
        default_params = config.get("default_params", {})
        self.search_model = BaseSearchModel(
            proxies=config.get("proxies", ""),
            timeout=60,
            default_params=default_params,
            allow_third_party_image_host=config.get(
                "allow_third_party_image_host", True
            ),
        )
        self.state_handlers = {
            "waiting_engine": self._handle_waiting,
            "waiting_both": self._handle_waiting,
            "waiting_image": self._handle_waiting,
        }

        # 注册 LLM 工具
        try:
            from .ReverseSearcher.tools.search_tools import register_search_tools

            register_search_tools(self)
            logger.info("[ReverseSearcher] LLM 搜图工具注册完成")
        except Exception:
            logger.exception("[ReverseSearcher] 工具注册失败")

    async def _collect_input_images(self, event: AstrMessageEvent) -> list[io.BytesIO]:
        """收集图片（BytesIO格式），支持直接发送和引用回复"""
        images = []

        # 1. 检查当前消息中的图片
        curr_url = get_img_urls(event.message_obj)
        if curr_url:
            imgs = await self.get_imgs([curr_url])
            if imgs:
                images.extend(imgs)
            else:
                logger.warning(
                    f"[ReverseSearcher] 消息含图片但下载失败: {curr_url[:100]}"
                )
        else:
            comps = [
                f"{type(c).__name__}(file={getattr(c, 'file', '')[:40]}, "
                f"url={getattr(c, 'url', '')[:40]})"
                for c in getattr(event.message_obj, "message", [])
            ]
            logger.warning(f"[ReverseSearcher] 未从消息提取到图片 URL，组件链: {comps}")

        # 2. 检查引用回复：框架已把被引用消息解析为 Reply 组件，
        #    其 chain 字段携带原消息的组件链（aiocqhttp 适配器 get_reply=True 时自动填充）
        if not images:
            for component in getattr(event.message_obj, "message", []) or []:
                if not isinstance(component, Reply):
                    continue
                reply_urls = []
                for comp in component.chain or []:
                    if isinstance(comp, AstrImage):
                        img_ref = (
                            getattr(comp, "url", "") or getattr(comp, "file", "") or ""
                        )
                        if img_ref:
                            reply_urls.append(img_ref)
                if reply_urls:
                    images.extend(await self.get_imgs(reply_urls))
                    break

        return images

    async def cleanup_loop(self):
        """
        定时清理超时无响应的用户状态数据

        异常:
            无（彻底失效的用户会被字典剔除）
        """
        while True:
            await asyncio.sleep(600)
            now = time.time()
            to_delete = [
                user_id
                for user_id, state in list(self.user_states.items())
                if now - state["timestamp"] > self.search_params_timeout
            ]
            for user_id in to_delete:
                del self.user_states[user_id]

    async def terminate(self):
        """
        插件关闭时收尾操作：关闭http连接与定时清理任务

        异常:
            无
        """
        await self.client.aclose()
        if hasattr(self, "cleanup_task"):
            self.cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.cleanup_task

    async def _download_img(self, url: str):
        """
        异步下载图片数据，转为BytesIO对象

        支持两种来源（均经过安全校验）：
        - 本地文件路径（仅限 AstrBot 数据目录内；QQ 官方等平台会把图片
          提前下载到 data/temp/，file 字段是本地路径）
        - 网络 URL（仅公网 http/https，拒绝内网/元数据地址；手动逐跳
          校验重定向，防止跳转到内网）

        参数:
            url (str): 图片URL或本地路径

        返回:
            io.BytesIO or None: 成功则为图片数据流，否则None

        异常:
            网络异常会吞掉，返回None
        """
        try:
            # 本地文件路径：仅允许 AstrBot 数据目录内（防任意本地文件读取）
            if url and is_safe_local_image_path(url):
                with open(url, "rb") as f:
                    return io.BytesIO(f.read())
            # 网络 URL：SSRF 防护（公网主机 + 手动逐跳校验重定向）
            if url and await asyncio.to_thread(is_safe_image_url, url):
                resp = await self._safe_get(url)
                if resp is not None and resp.status_code == 200:
                    return io.BytesIO(resp.content)
        except Exception as e:
            logger.debug(f"下载图片失败 {url}: {e}")
        return None

    async def _safe_get(self, url: str, max_redirects: int = 3):
        """
        手动跟随重定向下载，逐跳校验目标地址安全性

        防止攻击者用公网 URL 302 跳转到内网/元数据地址（重定向型 SSRF）。

        参数:
            url (str): 起始 URL
            max_redirects (int): 最大重定向跳数

        返回:
            httpx.Response or None: 最终响应；任一跳不安全/超限返回None
        """
        current = url
        for _ in range(max_redirects + 1):
            if not await asyncio.to_thread(is_safe_image_url, current):
                logger.debug(f"[security] 拦截不安全地址: {current[:80]}")
                return None
            try:
                resp = await self.client.get(
                    current, timeout=15, follow_redirects=False
                )
            except Exception as e:
                logger.debug(f"请求失败 {current[:80]}: {e}")
                return None
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                if not location:
                    return resp
                current = urljoin(current, location)
                continue
            return resp
        logger.debug(f"[security] 重定向次数超限: {url[:80]}")
        return None

    async def get_imgs(self, img_urls: list[str]) -> list[io.BytesIO]:
        """
        批量并发下载多张图片

        参数:
            img_urls (List[str]): 目标URL列表

        返回:
            List[io.BytesIO]: 所有获取成功的图片流集合

        异常:
            无
        """
        if not img_urls:
            return []
        imgs = await asyncio.gather(*[self._download_img(url) for url in img_urls])
        return [img for img in imgs if img is not None]

    async def _send_image(self, event: AstrMessageEvent, content: bytes):
        """
        以临时文件方式向目标事件发送图片消息

        参数:
            event: 事件对象
            content: 图片二进制内容

        返回:
            yield消息发送结果

        异常:
            无
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        try:
            yield event.chain_result([AstrImage.fromFileSystem(temp_file_path)])
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    async def _send_engine_intro(self, event: AstrMessageEvent):
        """
        绘制并发送引擎表格介绍图片（HTML 模板优先，云端 t2i 不可达时降级 PIL）

        参数:
            event: 事件对象

        返回:
            yield发送图片

        异常:
            无
        """
        if not self.available_engines:
            return

        # ── HTML 模板渲染（优先）──
        from astrbot.core import html_renderer

        from .ReverseSearcher.utils.templates import ENGINE_INTRO_TMPL

        engines_data = []
        for engine in self.available_engines:
            info = ENGINE_INFO[engine]
            engine_def = ENGINE_REGISTRY.get(engine)
            engines_data.append(
                {
                    "label": engine_def.label if engine_def else engine,
                    "url": info["url"],
                    "anime": info["anime"],
                    "keyword": self._get_keyword_for(engine),
                }
            )
        try:
            img_path = await asyncio.wait_for(
                html_renderer.render_custom_template(
                    ENGINE_INTRO_TMPL,
                    {"engines": engines_data},
                    return_url=False,
                    options={"full_page": True, "type": "jpeg", "quality": 80},
                ),
                timeout=25,
            )
            if img_path:
                with open(img_path, "rb") as f:
                    content = f.read()
                async for result in self._send_image(event, content):
                    yield result
                return
        except Exception as e:
            logger.warning(f"[ReverseSearcher] 引擎表格 HTML 渲染失败，降级 PIL: {e}")

        # ── PIL 回退 ──
        img_bytes = await asyncio.to_thread(
            create_engine_intro_image,
            self.available_engines,
            self._get_keyword_for,
        )
        async for result in self._send_image(event, img_bytes):
            yield result

    async def _perform_search(
        self, event: AstrMessageEvent, engine: str, img_buffer: io.BytesIO
    ):
        """
        调用模型执行图片反向搜索（含异常提示图渲染）
        参数:
            event: 消息事件对象
            engine: 引擎名称
            img_buffer: 图片二进制流

        返回:
            yield图片/提示

        异常:
            出错时生成错误提示图片
        """

        # 压缩源图：大图上传搜索 API 慢（用户反馈），统一缩到最长边 1500px 转 JPEG
        file_bytes = await self._prepare_image_bytes(img_buffer)

        # search_and_draw 内部已处理异常 → 返回错误图片
        result_img = await self.search_model.search_and_draw(
            api=engine, file=file_bytes
        )

        def encode_image():
            output = io.BytesIO()
            result_img.save(output, format="JPEG", quality=85)
            output.seek(0)
            return output.getvalue()

        img_bytes = await asyncio.to_thread(encode_image)
        async for result in self._send_image(event, img_bytes):
            yield result

    async def _prepare_image_bytes(
        self, img_buffer: io.BytesIO, max_side: int = 1500
    ) -> bytes:
        """压缩图片字节：最长边 ≤ max_side，转 JPEG 质量 88。

        大图直接上传到搜索 API 会显著拖慢搜索（用户实测：小图正常、大图慢）。
        1500px + JPEG 88 对角色/出处识别足够，上传体积可降 90%+。
        压缩失败回退原图。
        """

        def compress() -> bytes:
            img_buffer.seek(0)
            img = Image.open(img_buffer)
            img.load()
            w, h = img.size
            if max(w, h) > max_side:
                ratio = max_side / max(w, h)
                img = img.resize(
                    (max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS
                )
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
            return buf.getvalue()

        try:
            return await asyncio.to_thread(compress)
        except Exception as e:
            logger.warning(f"[ReverseSearcher] 图片压缩失败，使用原图: {e}")
            img_buffer.seek(0)
            return img_buffer.getvalue()

    async def _send_engine_prompt(self, event: AstrMessageEvent, state: dict):
        """
        按状态发送引擎选择或图片上传提示

        参数:
            event: 当前事件
            state: 用户状态

        返回:
            yield文本或图片提示

        异常:
            无
        """
        if not self.available_engines:
            yield event.plain_result(
                "当前没有可用的搜索引擎，请联系管理员在配置中启用至少一个引擎"
            )
            return
        example_engine = self.available_engines[0]
        # 已经提醒过就不再发完整提示，只发简短引导
        if state.get("prompted"):
            return
        if not state.get("engine"):
            async for result in self._send_engine_intro(event):
                yield result
        if state.get("preloaded_img"):
            yield event.plain_result(
                f"图片已接收，请选择引擎（回复引擎名或关键词，如 {example_engine} 或 a），{self.search_params_timeout}秒内有效"
            )
        elif state.get("engine"):
            yield event.plain_result(
                f"已选择引擎: {state['engine']}，请发送图片或图片URL，{self.search_params_timeout}秒内有效"
            )
        else:
            yield event.plain_result(
                f"请选择引擎（回复引擎名或关键词，如 {example_engine} 或 a）并发送图片，{self.search_params_timeout}秒内有效"
            )
        state["prompted"] = True

    async def _handle_timeout(self, event: AstrMessageEvent, user_id: str):
        """
        响应超时操作，移除用户状态并提示取消

        参数:
            event: 消息事件
            user_id: 目标用户ID

        返回:
            yield文本提示

        异常:
            无
        """
        yield event.plain_result("等待超时，操作取消")
        if user_id in self.user_states:
            del self.user_states[user_id]
        event.stop_event()

    def _get_engine_by_name(self, engine_name: str) -> str:
        """
        根据引擎名称或关键词获取实际的引擎标识符

        参数:
            engine_name: 引擎名称或关键词

        返回:
            str: 实际的引擎标识符，如果未找到则返回原名称
        """
        engine_name_lower = engine_name.lower()
        if engine_name_lower in self.engine_keywords:
            return self.engine_keywords[engine_name_lower]
        return engine_name

    def _get_keyword_for(self, engine: str) -> str:
        """获取引擎的自定义触发关键词；未配置时返回引擎名本身。"""
        for custom_keyword, engine_name in self.engine_keywords.items():
            if engine_name == engine:
                return custom_keyword
        return engine

    def _clear_waiting_states_before_search(self, user_id: str):
        """
        在执行搜索前清除用户等待状态

        参数:
            user_id: 用户ID

        返回:
            无

        异常:
            无
        """
        if user_id in self.user_states:
            del self.user_states[user_id]

    # ── 统一搜索解析器 ──────────────────────────────

    async def _resolve_and_search(
        self, event: AstrMessageEvent, state: dict, user_id: str
    ):
        """统一解析用户输入，尝试补全缺失参数并执行搜索

        三个等待处理器共享此核心逻辑：
        - 尝试从消息文本提取引擎名
        - 尝试从消息提取图片
        - 齐了 → 执行搜索
        - 缺 → 提示并更新状态
        """
        example_engine = (
            self.available_engines[0] if self.available_engines else "animetrace"
        )
        message_text = get_message_text(event.message_obj).strip()
        collected_imgs = await self._collect_input_images(event)

        # 1. 收集图片
        img_buffer = None
        if collected_imgs:
            img_buffer = collected_imgs[0]
        elif await asyncio.to_thread(is_image_url, message_text):
            img_buffer = await self._download_img(message_text)
        if img_buffer and not state.get("preloaded_img"):
            state["preloaded_img"] = img_buffer

        # 2. 收集引擎名（仅当状态中无引擎时）
        if not state.get("engine") and message_text:
            actual_engine = self._get_engine_by_name(message_text.lower())
            if actual_engine in self.available_engines:
                state["engine"] = actual_engine
            elif actual_engine in ALL_ENGINES:
                # 引擎被禁用
                yield event.plain_result(
                    f"引擎 '{message_text}' 已被禁用，请联系管理员在配置中启用或选择其他引擎（如{example_engine}）"
                )
                state["timestamp"] = time.time()
                async for result in self._send_engine_prompt(event, state):
                    yield result
                return
            elif not await asyncio.to_thread(is_image_url, message_text):
                # 无效引擎名（非引擎非URL）
                state.setdefault("invalid_attempts", 0)
                state["invalid_attempts"] += 1
                if state["invalid_attempts"] >= 2:
                    yield event.plain_result("连续两次输入错误的引擎名，已取消操作")
                    del self.user_states[user_id]
                    return
                yield event.plain_result(
                    f"引擎 '{message_text}' 不存在，请回复有效的引擎名（如{example_engine}）"
                )
                state["timestamp"] = time.time()
                async for result in self._send_engine_prompt(event, state):
                    yield result
                return

        # 3. 决策
        has_engine = bool(state.get("engine"))
        has_img = bool(state.get("preloaded_img"))

        if has_engine and has_img:
            # 齐了，执行搜索
            self._clear_waiting_states_before_search(user_id)
            try:
                async for result in self._perform_search(
                    event, state["engine"], state["preloaded_img"]
                ):
                    yield result
            except Exception as e:
                logger.warning(
                    f"[ReverseSearcher] 搜索失败: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                yield event.plain_result(f"搜索失败: {e}")
            return

        # 4. 缺参数 → 提示（已提醒过则跳过）
        state["timestamp"] = time.time()
        if not state.get("prompted"):
            if has_engine:
                yield event.plain_result(
                    f"已选择引擎: {state['engine']}，请发送图片，{self.search_params_timeout}秒内有效"
                )
            elif has_img:
                yield event.plain_result(
                    f"图片已接收，请回复有效的引擎名（如{example_engine}）"
                )
            else:
                yield event.plain_result(f"请提供引擎名（如{example_engine}）和图片")
            state["prompted"] = True
        async for result in self._send_engine_prompt(event, state):
            yield result

    # ── 薄封装处理器 ──────────────────────────────

    async def _handle_waiting(self, event: AstrMessageEvent, state: dict, user_id: str):
        async for result in self._resolve_and_search(event, state, user_id):
            yield result
        event.stop_event()

    async def _parse_initial_command(self, event: AstrMessageEvent):
        """
                解析初始搜索命令中的引擎名称和图片

                参数:
                    event: 消息事件对象

                返回:
                    tuple: (引擎名称或None, 图片缓冲区或None, 错误信息字典或None)
                        - 引擎名称: 有效的引擎名称或None
                        - 图片缓冲区: 图片数据的BytesIO对象或None
                        - 错误信息: 包含错误类型和相关信息的字典或None
                            {
        'type': 'invalid_engine' | 'disabled_engine',
        'engine_name': 输入的引擎名称,
        'message': 错误提示消息
                            }
        """
        example_engine = self.available_engines[0] if self.available_engines else None
        message_text = get_message_text(event.message_obj)
        parts = message_text.strip().split()
        engine = None
        error = None
        url_from_text = None
        if len(parts) > 1:
            if await asyncio.to_thread(is_image_url, parts[1]):
                url_from_text = parts[1]
            else:
                potential_engine = parts[1].lower()
                actual_engine = self._get_engine_by_name(potential_engine)
                if actual_engine in self.available_engines:
                    engine = actual_engine
                elif actual_engine in ALL_ENGINES:
                    error = {
                        "type": "disabled_engine",
                        "engine_name": potential_engine,
                        "message": f"引擎 '{potential_engine}' 已被禁用，请联系管理员在配置中启用或选择其他引擎（如{example_engine}）",
                    }
                else:
                    error = {
                        "type": "invalid_engine",
                        "engine_name": potential_engine,
                        "message": f"引擎 '{potential_engine}' 不存在，请提供有效的引擎名（如{example_engine}）",
                    }
                if len(parts) > 2 and await asyncio.to_thread(is_image_url, parts[2]):
                    url_from_text = parts[2]
        # Try to collect images using new logic
        img_buffer = None
        collected_imgs = await self._collect_input_images(event)

        # Original logic fallback specifically for text-embedded URL which _collect_input_images might not prioritizing if not in image component
        # But _collect_input_images does check get_img_urls.
        # But here we also support "engine image_url" syntax in text parts[1] or parts[2].

        if collected_imgs:
            img_buffer = collected_imgs[0]
        elif url_from_text:
            img_buffer = await self._download_img(url_from_text)

        return engine, img_buffer, error

    async def _handle_initial_search_command(
        self, event: AstrMessageEvent, user_id: str
    ):
        """
        处理最初 "以图搜图" 命令自动分流与预处理

        参数:
            event: 消息事件
            user_id: 用户ID

        返回:
            yield提示或结果

        异常:
            无
        """
        if not self.available_engines:
            yield event.plain_result(
                "当前没有可用的搜索引擎，请联系管理员在配置中启用至少一个引擎"
            )
            event.stop_event()
            return
        if user_id in self.user_states:
            del self.user_states[user_id]
        engine, img_buffer, error = await self._parse_initial_command(event)
        if error:
            state = {
                "step": "waiting_both",
                "timestamp": time.time(),
                "preloaded_img": img_buffer,
                "engine": None,
            }
            if error["type"] == "invalid_engine":
                state["invalid_attempts"] = 1
            self.user_states[user_id] = state
            yield event.plain_result(error["message"])
            async for result in self._send_engine_prompt(event, state):
                yield result
            event.stop_event()
            return
        if engine and img_buffer:
            self._clear_waiting_states_before_search(user_id)
            try:
                async for result in self._perform_search(event, engine, img_buffer):
                    yield result
            except Exception as e:
                logger.warning(
                    f"[ReverseSearcher] 搜索失败: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                yield event.plain_result(f"搜索失败: {e}")
            event.stop_event()
            return
        state = {
            "step": "waiting_both",
            "timestamp": time.time(),
            "preloaded_img": img_buffer,
            "engine": engine,
        }
        self.user_states[user_id] = state
        async for result in self._send_engine_prompt(event, state):
            yield result
        event.stop_event()

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """私聊消息入口，委托给统一处理逻辑"""
        async for result in self._on_message_impl(event):
            yield result

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """群聊消息入口，委托给统一处理逻辑"""
        async for result in self._on_message_impl(event):
            yield result

    async def _on_message_impl(self, event: AstrMessageEvent):
        """
        插件消息收发主入口，处理各种状态下用户输入分发
        """
        user_id = event.get_sender_id()
        message_text = get_message_text(event.message_obj)

        # 检查是否以任意一个触发关键词开头（且开关开启）
        if any(
            message_text.strip().startswith(keyword)
            for keyword in self.trigger_keywords
        ):
            if not self.enable_keyword_trigger:
                return  # 关键词触发已关闭
            async for result in self._handle_initial_search_command(event, user_id):
                yield result
            return
        state = self.user_states.get(user_id)
        if not state:
            return
        if time.time() - state["timestamp"] > self.search_params_timeout:
            async for result in self._handle_timeout(event, user_id):
                yield result
            return
        handler = self.state_handlers.get(state.get("step"))
        if handler:
            async for result in handler(event, state, user_id):
                yield result
