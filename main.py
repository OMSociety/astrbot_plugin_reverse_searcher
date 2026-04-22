import asyncio
import io
import os
import re
import tempfile
import time
from typing import List
from pathlib import Path
import httpx
from PIL import Image, ImageDraw, ImageFont
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image as AstrImage, Nodes, Node, Plain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import base64
import socket
import ipaddress
from urllib.parse import urlparse
from .ReverseSearcher.model import BaseSearchModel

ALL_ENGINES = [
    "animetrace", "yandex", "ehentai", "google", "saucenao"
]

ENGINE_INFO = {
    "animetrace": {"url": "https://www.animetrace.com/", "anime": True},
    "yandex": {"url": "https://yandex.com/images/", "anime": False},    "ehentai": {"url": "https://e-hentai.org/", "anime": True},
    "google": {"url": "https://lens.google.com/", "anime": False},
    "saucenao": {"url": "https://saucenao.com/", "anime": True},
}

COLOR_THEME = {
    "bg": (255, 255, 255),
    "header_bg": (67, 99, 216),
    "header_text": (255, 255, 255),
    "table_header": (240, 242, 245),
    "cell_bg_even": (250, 250, 252),
    "cell_bg_odd": (255, 255, 255),
    "border": (180, 185, 195),
    "text": (50, 50, 50),
    "url": (41, 98, 255),
    "success": (76, 175, 80),
    "fail": (244, 67, 54),
    "shadow": (0, 0, 0, 30),
    "hint": (100, 100, 100)
}

def is_image_url(text: str) -> bool:
    """
    判断文本是否为图片URL（http开头，常见图片扩展名结尾）

    参数:
        text (str): 待检测文本

    返回:
        bool: 是图片则True，否则False

    异常:
        无
    """
    return bool(re.match(r"^https://.*\.(jpg|jpeg|png|gif|webp|bmp)$", text, re.IGNORECASE))

def split_text_by_length(text: str, max_length: int = 4000) -> List[str]:
    """
    按最大长度将长文本智能断行拆分，优先按50连字符切分

    参数:
        text (str): 待分割文本
        max_length (int): 每段最大长度

    返回:
        List[str]: 拆分碎片

    异常:
        无
    """
    if len(text) <= max_length:
        return [text]
    separator = "-" * 50
    result = []
    while text:
        if len(text) <= max_length:
            result.append(text)
            break
        cut_index = max_length
        separator_index = text.rfind(separator, 0, max_length)
        if separator_index != -1 and separator_index > max_length // 2:
            cut_index = separator_index + len(separator)
        result.append(text[:cut_index])
        text = text[cut_index:]
    return result

def get_img_urls(message) -> str:
    """
    从消息对象中提取第一张图片的URL

    参数:
        message: 消息体对象，可含message或raw_message属性

    返回:
        str: 图片URL，如果没有找到则返回空字符串

    异常:
        无
    """
    raw_message = getattr(message, 'raw_message', '')
    if isinstance(raw_message, dict) and "message" in raw_message:
        raw_message_str = str(raw_message.get("message", []))
        image_match = re.search(r"'type':\s*'image'.*?'url':\s*'([^']+)'", raw_message_str)
        if image_match:
            return image_match.group(1)
        file_match = re.search(r"'type':\s*'file'.*?'file':\s*'([^']+)'", raw_message_str)
        if file_match:
            filename = file_match.group(1)
            IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
            if os.path.splitext(filename.lower())[1] in IMAGE_EXTS:
                for component in getattr(message, 'message', []):
                    component_str = str(component)
                    if "type='File'" in component_str:
                        url_match = re.search(r"url='([^']+)'", component_str)
                        if url_match:
                            return url_match.group(1)
    for component in getattr(message, 'message', []):
        component_str = str(component)
        if "type='Image'" in component_str:
            url_match = re.search(r"url='([^']+)'", component_str)
            if url_match:
                return url_match.group(1)
    return ""

def get_message_text(message) -> str:
    """
    提取消息对象中的文本内容（忽略图片和其他非文本消息段落）

    参数:
        message: 消息体对象

    返回:
        str: 提取到的文本内容（去首尾空格）

    异常:
        无
    """
    raw_message = getattr(message, 'raw_message', '')
    if isinstance(raw_message, str):
        return raw_message.strip()
    elif isinstance(raw_message, dict) and "message" in raw_message:
        texts = [
            (msg_part.get("data", {}).get("text", "") if isinstance(msg_part, dict) else str(msg_part))
            for msg_part in raw_message.get("message", [])
            if (isinstance(msg_part, dict) and msg_part.get("type") == "text") or isinstance(msg_part, str)
        ]
        return " ".join(texts).strip()
    return ''


@register("astrbot_plugin_img_rev_searcher", "drdon1234", "以图搜图，找出处", "3.4")
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
            text_confirm_timeout: 等待文本格式确认的超时时间（秒）
            search_model: 搜索执行模型
            state_handlers: 状态处理器方法字典

        返回:
            无

        异常:
            无
        """
        super().__init__(context)
        self.client = httpx.AsyncClient()
        self.user_states = {}
        self.cleanup_task = asyncio.create_task(self.cleanup_loop())
        available_apis_config = config.get("available_apis", {})
        self.available_engines = [e for e in ALL_ENGINES if available_apis_config.get(e, True)]
        timeout_settings = config.get("timeout_settings", {})
        self.search_params_timeout = timeout_settings.get("search_params_timeout", 30)
        self.text_confirm_timeout = timeout_settings.get("text_confirm_timeout", 30)
        keyword_config = config.get("keyword", {})
        trigger_keywords = keyword_config.get("trigger_keywords", ["以图搜图"])
        # 确保触发关键词是列表格式，如果为空或无效则使用默认值
        if isinstance(trigger_keywords, list) and trigger_keywords:
            self.trigger_keywords = [kw.strip() for kw in trigger_keywords if kw and kw.strip()]
        else:
            self.trigger_keywords = ["以图搜图"]
        self.auto_send_text_results = config.get("auto_send_text_results", False)
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
            default_cookies=config.get("default_cookies", {})
        )
        self.state_handlers = {
            "waiting_text_confirm": self._handle_waiting_text_confirm,
            "waiting_engine": self._handle_waiting_engine,
            "waiting_both": self._handle_waiting_both,
            "waiting_image": self._handle_waiting_image,
            "waiting_mode_selection": self._handle_waiting_mode_selection,
        }

        # 注册 LLM 工具
        try:
            from ReverseSearcher.tools.search_tools import register_search_tools
            register_search_tools(self)
        except Exception as e:
            import sys
            sys.stderr.write(f"[ReverseSearcher] 工具注册失败: {e}\n")


    @staticmethod
    def _is_safe_url(url: str) -> bool:
        """
        检查 URL 是否安全 (防止 SSRF)
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            
            hostname = parsed.hostname
            if not hostname:
                return False
                
            # 获取 IP 地址
            try:
                addr_info = socket.getaddrinfo(hostname, None)
            except socket.gaierror:
                return False
                
            for family, socktype, proto, canonname, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                # 禁止以下类型的 IP
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                    # logger.warning(f"检测到不安全的 IP 地址: {ip_str} ({hostname})")
                    return False
            
            return True
        except Exception as e:
            # logger.warning(f"URL 安全检查失败: {e}")
            return False

    async def _fetch_reply_images_via_api(self, event: AstrMessageEvent, reply_id: str) -> List[io.BytesIO]:
        """通过 OneBot API 获取被引用消息中的图片"""
        images = []
        try:
            # 尝试获取底层 client 并调用 get_msg API
            client = None
            
            # 方式1：从 event.raw_event 获取 bot 实例
            if hasattr(event, 'raw_event') and event.raw_event:
                raw = event.raw_event
                if hasattr(raw, 'bot'):
                    client = raw.bot
                elif hasattr(raw, '_bot'):
                    client = raw._bot
            
            # 方式2：从 context 获取
            if not client and hasattr(self, 'context') and self.context:
                # AstrBot 3.4+
                if hasattr(self.context, 'get_platform_client'):
                    client = self.context.get_platform_client()
                elif hasattr(self.context, 'platform_manager'):
                    pm = self.context.platform_manager
                    if hasattr(pm, 'get_client'):
                        client = pm.get_client('aiocqhttp')
            
            if not client:
                return images
            
            # 调用 get_msg API
            result = None
            if hasattr(client, 'call_api'):
                result = await client.call_api('get_msg', message_id=int(reply_id))
            elif hasattr(client, 'get_msg'):
                result = await client.get_msg(message_id=int(reply_id))
            
            if not result:
                return images
            
            # 解析返回的消息
            message_content = None
            if isinstance(result, dict):
                message_content = result.get('message', [])
            elif hasattr(result, 'message'):
                message_content = result.message
            
            if not message_content:
                return images
            
            urls = []
            for seg in message_content:
                seg_type = None
                seg_data = None
                
                if isinstance(seg, dict):
                    seg_type = seg.get('type')
                    seg_data = seg.get('data', {})
                elif hasattr(seg, 'type'):
                    seg_type = seg.type
                    seg_data = getattr(seg, 'data', {})
                
                if seg_type == 'image':
                    img_url = None
                    if isinstance(seg_data, dict):
                        img_url = seg_data.get('url') or seg_data.get('file')
                    elif hasattr(seg_data, 'url'):
                        img_url = seg_data.url
                    
                    if img_url and self._is_safe_url(img_url):
                        urls.append(img_url)
            
            if urls:
                images = await self.get_imgs(urls)
        except Exception as e:
            logger.warning(f"通过 API 获取被引用消息失败: {e}")
        
        return images

    async def _collect_input_images(self, event: AstrMessageEvent) -> List[io.BytesIO]:
        """收集图片（BytesIO格式），支持直接发送和引用"""
        images = []
        reply_id = None
        reply_images_found = False

        # 1. 检查当前消息中的图片
        # 兼容旧逻辑 get_img_urls
        curr_url = get_img_urls(event.message_obj)
        if curr_url:
            imgs = await self.get_imgs([curr_url])
            if imgs:
                images.extend(imgs)

        # 2. 检查引用
        if hasattr(event, "message_obj") and event.message_obj and hasattr(event.message_obj, "message"):
             for comp in event.message_obj.message:
                # AstrBot 的 Reply 组件
                if hasattr(comp, 'type') and comp.type == 'Reply': # Check type name if strict
                    pass
                # Check for Reply component structure
                if isinstance(comp, Nodes): continue # Skip nodes
                
                # Check if it is a Reply object or has id/data['id']
                # The user reference code checks isinstance(comp, Reply) but we don't have Reply imported easily? 
                # Actually imported from astrbot.core.message.components but let's be duck-typed or check attributes
                
                c_id = getattr(comp, 'id', None)
                if not c_id and hasattr(comp, 'data') and isinstance(comp.data, dict):
                    c_id = comp.data.get('id')
                
                # In Astrbot, usually Repy component has .id
                # Let's check if the component string repr has 'reply' logic or check event.message_obj for specific structure
                pass

        # Use robust extraction from raw_message for reply ID
        # AstrBot/aiocqhttp logic: raw_event might be the dict we saw in logs
        raw_evt = getattr(event, 'raw_event', None)
        if raw_evt and isinstance(raw_evt, dict):
             msg_segs = raw_evt.get('message', [])
             if isinstance(msg_segs, list):
                 for seg in msg_segs:
                     if seg.get('type') == 'reply':
                         reply_id = seg.get('data', {}).get('id')
                         break


        if reply_id and not images:
             # Fetch from API
             fetched = await self._fetch_reply_images_via_api(event, reply_id)
             if fetched:
                 images.extend(fetched)
        
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
                user_id for user_id, state in list(self.user_states.items())
                if now - state['timestamp'] > self.search_params_timeout
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
        if hasattr(self, 'cleanup_task'):
            self.cleanup_task.cancel()

    async def _download_img(self, url: str):
        """
        异步下载图片数据，转为BytesIO对象

        参数:
            url (str): 图片URL

        返回:
            io.BytesIO or None: 成功则为图片数据流，否则None

        异常:
            网络异常会吞掉，返回None
        """
        try:
            r = await self.client.get(url, timeout=15)
            if r.status_code == 200:
                return io.BytesIO(r.content)
        except Exception:
            pass
        return None

    async def get_imgs(self, img_urls: List[str]) -> List[io.BytesIO]:
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
        绘制并发送引擎表格介绍图片，便于用户首次选择

        参数:
            event: 事件对象

        返回:
            yield发送图片

        异常:
            无
        """
        def create_engine_intro_image():
            width = 1000
            cell_height = 50
            header_height = 60
            title_height = 70
            table_height = header_height + cell_height * len(self.available_engines)
            height = title_height + table_height + 25
            border_width = 2
            
            def rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=1):
                x1, y1, x2, y2 = xy
                diameter = 2 * radius
                draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill, outline=outline, width=width)
                draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill, outline=outline, width=width)
                draw.pieslice([x1, y1, x1 + diameter, y1 + diameter], 180, 270, fill=fill, outline=outline, width=width)
                draw.pieslice([x2 - diameter, y1, x2, y1 + diameter], 270, 360, fill=fill, outline=outline, width=width)
                draw.pieslice([x1, y2 - diameter, x1 + diameter, y2], 90, 180, fill=fill, outline=outline, width=width)
                draw.pieslice([x2 - diameter, y2 - diameter, x2, y2], 0, 90, fill=fill, outline=outline, width=width)

            img = Image.new('RGB', (width, height), COLOR_THEME["bg"])
            draw = ImageDraw.Draw(img)
            workspace_root = Path(__file__).parent
            try:
                font_path = str(workspace_root / "resource/font/arialuni.ttf")
                title_font = ImageFont.truetype(font_path, 24)
                header_font = ImageFont.truetype(font_path, 18)
                body_font = ImageFont.truetype(font_path, 16)
            except Exception:
                title_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                body_font = ImageFont.load_default()
            rounded_rectangle(draw, [20, 15, width - 20, title_height - 5], 10, fill=COLOR_THEME["header_bg"])
            title = "可用搜索引擎"
            title_width = draw.textlength(title, font=title_font) if hasattr(draw, 'textlength') else title_font.getsize(title)[0]
            title_x = (width - title_width) // 2
            draw.text((title_x, 25), title, font=title_font, fill=COLOR_THEME["header_text"])
            table_x = 20
            table_width = width - 40
            col_widths = [int(table_width * 0.15), int(table_width * 0.40), int(table_width * 0.20), int(table_width * 0.25)]
            table_y = title_height + 10
            table_bottom = table_y + header_height + cell_height * len(self.available_engines)
            draw.rectangle([table_x, table_y, table_x + sum(col_widths), table_y + header_height], fill=COLOR_THEME["table_header"])
            y = table_y + header_height
            for idx, engine in enumerate(self.available_engines):
                if engine not in ENGINE_INFO:
                    continue
                row_bg = COLOR_THEME["cell_bg_even"] if idx % 2 == 0 else COLOR_THEME["cell_bg_odd"]
                draw.rectangle([table_x, y, table_x + sum(col_widths), y + cell_height], fill=row_bg)
                y += cell_height
            headers = ["引擎", "网址", "二次元图片专用", "关键词"]
            x = table_x
            for i, header in enumerate(headers):
                text_width = draw.textlength(header, font=header_font) if hasattr(draw, 'textlength') else header_font.getsize(header)[0]
                text_x = x + (col_widths[i] - text_width) // 2
                draw.text((text_x, table_y + (header_height - 18) // 2), header, font=header_font, fill=COLOR_THEME["text"])
                x += col_widths[i]
            y = table_y + header_height
            for idx, engine in enumerate(self.available_engines):
                if engine not in ENGINE_INFO:
                    continue
                info = ENGINE_INFO[engine]
                x = table_x
                draw.text((x + 15, y + (cell_height - 16) // 2), engine, font=body_font, fill=COLOR_THEME["text"])
                x += col_widths[0]
                draw.text((x + 15, y + (cell_height - 16) // 2), info["url"], font=body_font, fill=COLOR_THEME["url"])
                x += col_widths[1]
                mark = "✓" if info["anime"] else "✗"
                mark_color = COLOR_THEME["success"] if info["anime"] else COLOR_THEME["fail"]
                mark_width = draw.textlength(mark, font=header_font) if hasattr(draw, 'textlength') else header_font.getsize(mark)[0]
                draw.text((x + (col_widths[2] - mark_width) // 2, y + (cell_height - 18) // 2), mark, font=header_font, fill=mark_color)
                x += col_widths[2]
                keyword = engine
                for custom_keyword, engine_name in self.engine_keywords.items():
                    if engine_name == engine:
                        keyword = custom_keyword
                        break
                draw.text((x + 15, y + (cell_height - 16) // 2), keyword, font=body_font, fill=COLOR_THEME["hint"])
                y += cell_height
            draw.rectangle([table_x, table_y, table_x + sum(col_widths), table_bottom], outline=COLOR_THEME["border"], width=border_width)
            for i in range(1, len(self.available_engines) + 1):
                line_y = table_y + header_height + cell_height * i
                if i < len(self.available_engines):
                    draw.line([(table_x, line_y), (table_x + sum(col_widths), line_y)], fill=COLOR_THEME["border"], width=border_width)
            draw.line([(table_x, table_y + header_height), (table_x + sum(col_widths), table_y + header_height)], fill=COLOR_THEME["border"], width=border_width)
            col_x = table_x
            for i in range(len(col_widths) - 1):
                col_x += col_widths[i]
                draw.line([(col_x, table_y), (col_x, table_bottom)], fill=COLOR_THEME["border"], width=border_width)
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=85)
            output.seek(0)
            return output.getvalue()
        
        img_bytes = await asyncio.to_thread(create_engine_intro_image)
        async for result in self._send_image(event, img_bytes):
                yield result

    async def _handle_waiting_mode_selection(self, event: AstrMessageEvent, state: dict, user_id: str):
        """
        处理模式选择输入 (ASCII2D/IQDB)
        """
        message_text = get_message_text(event.message_obj).strip().lower()
        if not message_text:
            return

        engine = state.get("engine")
        extra_params = state.get("search_extra_params", {})
        
        if message_text in ["2", "bovw", "特征"]:
            extra_params["bovw"] = True
            await event.send(event.plain_result("已选择: 特征搜索 (Bovw)"))
        else:
            await event.send(event.plain_result("无效输入，请回复 1 (颜色) 或 2 (特征)"))
            return
        
        if message_text in ["2", "3d", "real"]:
            extra_params["is_3d"] = True
            await event.send(event.plain_result("已选择: 三次元 (3D)"))
        else:
            await event.send(event.plain_result("无效输入，请回复 1 (2D) 或 2 (3D)"))
            return
        
        # 更新参数并清除等待状态
        state["search_extra_params"] = extra_params
        state["mode_confirmed"] = True
        
        # 恢复图片数据 (从 state 中?)
        # 此时图片还没有被消费，或者需要重新获取?
        # _perform_search 需要 img_buffer
        # 我们需要在 _perform_search_check 中把 img_buffer 这里的逻辑串起来
        # 当前架构 _perform_search 是一次性调用
        # 这里我们直接调用 _perform_search 稍微麻烦，因为它需要 img_buffer
        # 我们可以把 img_buffer 暂时存在 state 已经被序列化了吗? No, state is dict.
        # ReverseSearcher 插件逻辑中 state 是存放在 self.user_states 内存中的
        # 所以我们可以把 BytesIO 暂存 (虽然不太好，暂时可行)
        
        img_buffer = state.get("img_buffer_ptr")
        if img_buffer:
            img_buffer.seek(0)
            async for result in self._perform_search(event, engine, img_buffer):
                yield result
        else:
            yield event.plain_result("图片数据丢失，请重新搜索")
        
        # 清理: 仅当状态仍为 waiting_mode_selection 时才删除
        # 如果 _perform_search 已经进入 waiting_text_confirm，则保留
        current = self.user_states.get(user_id)
        if current and current.get("step") == "waiting_mode_selection":
            del self.user_states[user_id]
        
        event.stop_event()

    async def _check_and_ask_mode(self, event: AstrMessageEvent, engine: str, img_buffer: io.BytesIO, user_id: str):
        """
        检查是否需要询问模式（预留接口，当前未使用）
        返回 True 表示已拦截并发送询问，False 表示直接继续
        """
        return False

    async def _perform_search(self, event: AstrMessageEvent, engine: str, img_buffer: io.BytesIO):
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

        file_bytes = img_buffer.getvalue()
        
        # 获取额外参数
        user_id = event.get_sender_id()
        state = self.user_states.get(user_id, {})
        extra_kwargs = state.get("search_extra_params", {})
        
        try:
             result_text = await self.search_model.search(api=engine, file=file_bytes, **extra_kwargs)
             if result_text is None:
                 yield event.plain_result(f"[{engine}] 未找到相关结果")
                 return
        except Exception as e:
             # Log the error for admin/debug
             logger.error(f"[{engine}] Search failed: {e}")
             import traceback
             logger.error(traceback.format_exc())
             
             # Notify user about the specific error
             yield event.plain_result(f"[{engine}] 搜索出错: {str(e)}")
             return
        img_buffer.seek(0)
        
        def process_image():
            try:
                source_image = Image.open(img_buffer)
                result_img = self.search_model.draw_results(engine, result_text, source_image)
            except Exception as e:
                result_img = self.search_model.draw_error(engine, str(e))
            output = io.BytesIO()
            result_img.save(output, format="JPEG", quality=85)
            output.seek(0)
            return output.getvalue()
        
        img_bytes = await asyncio.to_thread(process_image)
        async for result in self._send_image(event, img_bytes):
                yield result
        if self.auto_send_text_results:
            text_parts = split_text_by_length(result_text)
            sender_name = "图片搜索bot"
            sender_id = event.get_self_id()
            try:
                sender_id = int(sender_id)
            except Exception:
                pass
            for i, part in enumerate(text_parts):
                node = Node(
                    name=sender_name,
                    uin=sender_id,
                    content=[Plain(f"[  搜索结果 {i + 1} / {len(text_parts)}  ]\n\n{part}")]
                )
                nodes = Nodes([node])
                try:
                    await event.send(event.chain_result([nodes]))
                except Exception as e:
                    yield event.plain_result(f"发送搜索结果失败: {str(e)}")

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
            yield event.plain_result("当前没有可用的搜索引擎，请联系管理员在配置中启用至少一个引擎")
            return
        example_engine = self.available_engines[0]
        if not state.get('engine'):
            async for result in self._send_engine_intro(event):
                yield result
        if state.get('preloaded_img'):
            yield event.plain_result(f"图片已接收，请选择引擎（回复引擎名或关键词，如 {example_engine} 或 a），{self.search_params_timeout}秒内有效")
        elif state.get('engine'):
            yield event.plain_result(f"已选择引擎: {state['engine']}，请发送图片或图片URL，{self.search_params_timeout}秒内有效")
        else:
            yield event.plain_result(f"请选择引擎（回复引擎名或关键词，如 {example_engine} 或 a）并发送图片，{self.search_params_timeout}秒内有效")

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

    async def _handle_waiting_text_confirm(self, event: AstrMessageEvent, state: dict, user_id: str):
        """
        等待用户是否主动获取文本格式结果
        """
        message_text = get_message_text(event.message_obj).strip()
        
        if time.time() - state["timestamp"] > self.text_confirm_timeout:
            del self.user_states[user_id]
            event.stop_event()
            return

        # Check for Yes/Y/是
        if message_text.lower() in ["是", "y"]:
            text_parts = split_text_by_length(state["result_text"])
            sender_name = "图片搜索bot"
            sender_id = event.get_self_id()
            try:
                sender_id = int(sender_id)
            except Exception:
                pass
            
            for i, part in enumerate(text_parts):
                node = Node(
                    name=sender_name,
                    uin=sender_id,
                    content=[Plain(f"[  搜索结果 {i + 1} / {len(text_parts)}  ]\n\n{part}")]
                )
                nodes = Nodes([node])
                try:
                    await event.send(event.chain_result([nodes]))
                except Exception as e:
                    yield event.plain_result(f"发送搜索结果失败: {str(e)}")
            del self.user_states[user_id]
            event.stop_event()
            return

    async def _handle_waiting_engine(self, event: AstrMessageEvent, state: dict, user_id: str):
        """
        用户需要提供引擎名时的处理器

        参数:
            event: 消息事件
            state: 用户状态
            user_id: 用户ID

        返回:
            yield流程消息

        异常:
            输入错误会触发二次确认，超两次重试直接取消
        """
        example_engine = self.available_engines[0]
        message_text = get_message_text(event.message_obj).lower()
        if not message_text:
            # Check for image input
            collected_imgs = await self._collect_input_images(event)
            if collected_imgs:
                state["preloaded_img"] = collected_imgs[0]
                state["timestamp"] = time.time()
                yield event.plain_result(f"图片已接收，请回复有效的引擎名（如{example_engine}）")
                event.stop_event()
                return
            
            yield event.plain_result(f"请回复有效的引擎名（如{example_engine}）")
            state["timestamp"] = time.time()
            event.stop_event()
            return
        actual_engine = self._get_engine_by_name(message_text)
        if actual_engine in self.available_engines:
            state["engine"] = actual_engine
            if state.get("preloaded_img"):
                self._clear_waiting_states_before_search(user_id)
                try:
                    async for result in self._perform_search(event, state["engine"], state["preloaded_img"]):
                        yield result
                except Exception:
                    yield event.plain_result("搜索失败，请重试")
            else:
                state["step"] = "waiting_image"
                state["timestamp"] = time.time()
                yield event.plain_result(f"已选择引擎: {message_text}，请在{self.search_params_timeout}秒内发送一张图片，我会进行搜索")
        else:
            if actual_engine in ALL_ENGINES and actual_engine not in self.available_engines:
                yield event.plain_result(f"引擎 '{message_text}' 已被禁用，请联系管理员在配置中启用或选择其他引擎（如{example_engine}）")
                state["timestamp"] = time.time()
                async for result in self._send_engine_prompt(event, state):
                    yield result
            else:
                state.setdefault("invalid_attempts", 0)
                state["invalid_attempts"] += 1
                if state["invalid_attempts"] >= 2:
                    yield event.plain_result("连续两次输入错误的引擎名，已取消操作")
                    del self.user_states[user_id]
                else:
                    yield event.plain_result(f"引擎 '{message_text}' 不存在，请回复有效的引擎名（如{example_engine}）")
                    state["timestamp"] = time.time()
                    async for result in self._send_engine_prompt(event, state):
                        yield result
        event.stop_event()

    async def _handle_waiting_both(self, event, state, user_id):
        """
        等待用户同时给出引擎与图片输入的处理逻辑

        参数:
            event: 事件对象
            state: 用户状态
            user_id: 用户ID

        返回:
            yield文本提示/搜索结果

        异常:
            无
        """
        example_engine = self.available_engines[0] if self.available_engines else None
        message_text = get_message_text(event.message_obj).lower()
        img_urls = get_img_urls(event.message_obj)
        updated = False
        if message_text and not state.get('engine'):
            actual_engine = self._get_engine_by_name(message_text)
            if actual_engine in self.available_engines:
                state["engine"] = actual_engine
                updated = True
            elif actual_engine in ALL_ENGINES:
                yield event.plain_result(
                    f"引擎 '{message_text}' 已被禁用，请联系管理员在配置中启用或选择其他引擎（如{example_engine}）"
                )
                async for result in self._send_engine_prompt(event, state):
                    yield result
                event.stop_event()
                return
            elif not is_image_url(message_text):
                state.setdefault("invalid_attempts", 0)
                state["invalid_attempts"] += 1
                if state["invalid_attempts"] >= 2:
                    yield event.plain_result("连续两次输入错误的引擎名，已取消操作")
                    del self.user_states[user_id]
                    event.stop_event()
                    return
                else:
                    yield event.plain_result(
f"引擎 '{message_text}' 不存在，请回复有效的引擎名（如{example_engine}）"
                    )
                    async for result in self._send_engine_prompt(event, state):
                        yield result
                    event.stop_event()
                    return
        # 尝试收集图片
        img_buffer = None
        collected_imgs = await self._collect_input_images(event)
        if collected_imgs:
            img_buffer = collected_imgs[0]
            if img_buffer and not state.get('preloaded_img'):
                 state["preloaded_img"] = img_buffer
                 updated = True
        elif is_image_url(message_text):
            img_buffer = await self._download_img(message_text)
            if img_buffer and not state.get('preloaded_img'):
                 state["preloaded_img"] = img_buffer
                 updated = True

        if state.get("engine") and state.get("preloaded_img"):
            self._clear_waiting_states_before_search(user_id)
            try:
                async for result in self._perform_search(event, state["engine"], state["preloaded_img"]):
                    yield result
            except Exception:
                yield event.plain_result("搜索失败，请重试")
            event.stop_event()
            return


        if updated:
            state["timestamp"] = time.time()
            async for result in self._send_engine_prompt(event, state):
                yield result
            event.stop_event()
            return
        state["timestamp"] = time.time()
        if not state.get('engine') and not state.get('preloaded_img'):
            yield event.plain_result(f"请提供引擎名（如{example_engine}）和图片")
        elif not state.get('engine'):
            yield event.plain_result(f"请提供引擎名（如{example_engine}）")
        elif not state.get('preloaded_img'):
            yield event.plain_result("请提供图片")
        event.stop_event()

    async def _handle_waiting_image(self, event: AstrMessageEvent, state: dict, user_id: str):
        """
        处理仅等待图片输入的用户状态

        参数:
            event: 消息事件
            state: 用户状态
            user_id: 用户ID

        返回:
            yield消息

        异常:
            无
        """
        img_buffer = None
        message_text = get_message_text(event.message_obj).strip()
        collected_imgs = await self._collect_input_images(event)
        if collected_imgs:
            img_buffer = collected_imgs[0]
        elif is_image_url(message_text):
            img_buffer = await self._download_img(message_text)
        if img_buffer:
            self._clear_waiting_states_before_search(user_id)
            async for result in self._perform_search(event, state["engine"], img_buffer):
                yield result
            event.stop_event()
        else:
            yield event.plain_result("请发送一张图片或图片链接")

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
        img_urls = get_img_urls(event.message_obj)
        parts = message_text.strip().split()
        engine = None
        img_buffer = None
        error = None
        url_from_text = None
        if len(parts) > 1:
            if is_image_url(parts[1]):
                url_from_text = parts[1]
            else:
                potential_engine = parts[1].lower()
                actual_engine = self._get_engine_by_name(potential_engine)
                if actual_engine in self.available_engines:
                    engine = actual_engine
                elif actual_engine in ALL_ENGINES:
                    error = {
'type': 'disabled_engine',
'engine_name': potential_engine,
'message': f"引擎 '{potential_engine}' 已被禁用，请联系管理员在配置中启用或选择其他引擎（如{example_engine}）"
                    }
                else:
                    error = {
'type': 'invalid_engine',
'engine_name': potential_engine,
'message': f"引擎 '{potential_engine}' 不存在，请提供有效的引擎名（如{example_engine}）"
                    }
                if len(parts) > 2 and is_image_url(parts[2]):
                    url_from_text = parts[2]
        # Try to collect images using new logic
        img_buffer = None
        collected_imgs = await self._collect_input_images(event)
        
        # Original logic fallback specifically for text-embedded URL which _collect_input_images might not prioritizing if not in image component
        # But _collect_input_images does check get_img_urls.
        # Let's check logic: _collect_input_images calls get_img_urls.
        # But here we also support "engine image_url" syntax in text parts[1] or parts[2].
        
        if collected_imgs:
            img_buffer = collected_imgs[0]
        elif url_from_text:
             img_buffer = await self._download_img(url_from_text)
             
        return engine, img_buffer, error

    async def _handle_initial_search_command(self, event: AstrMessageEvent, user_id: str):
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
            yield event.plain_result("当前没有可用的搜索引擎，请联系管理员在配置中启用至少一个引擎")
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
                "engine": None
            }
            if error['type'] == 'invalid_engine':
                state["invalid_attempts"] = 1  
            self.user_states[user_id] = state
            yield event.plain_result(error['message'])
            async for result in self._send_engine_prompt(event, state):
                yield result
            event.stop_event()
            return
        if engine and img_buffer:
            self._clear_waiting_states_before_search(user_id)
            try:
                async for result in self._perform_search(event, engine, img_buffer):
                    yield result
            except Exception:
                yield event.plain_result("搜索失败，请重试")
            event.stop_event()
            return
        state = {
            "step": "waiting_both",
            "timestamp": time.time(),
            "preloaded_img": img_buffer,
            "engine": engine
        }
        self.user_states[user_id] = state
        async for result in self._send_engine_prompt(event, state):
            yield result
        event.stop_event()

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        """
        插件消息收发主入口，处理各种状态下用户输入分发
        """
        user_id = event.get_sender_id()
        message_text = get_message_text(event.message_obj)
        
        # 检查是否以任意一个触发关键词开头（且开关开启）
        if any(message_text.strip().startswith(keyword) for keyword in self.trigger_keywords):
            if not self.enable_keyword_trigger:
                return  # 关键词触发已关闭
            async for result in self._handle_initial_search_command(event, user_id):
                yield result
            return
        state = self.user_states.get(user_id)
        if not state:
            return
        if state.get("step") == "waiting_text_confirm" and time.time() - state["timestamp"] > self.text_confirm_timeout:
            del self.user_states[user_id]
            event.stop_event()
            return
        if time.time() - state["timestamp"] > self.search_params_timeout:
            async for result in self._handle_timeout(event, user_id):
                yield result
            return
        handler = self.state_handlers.get(state.get("step"))
        if handler:
            async for result in handler(event, state, user_id):
                yield result
