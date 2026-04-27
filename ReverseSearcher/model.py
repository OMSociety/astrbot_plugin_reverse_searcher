import asyncio
import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .engine_registry import ENGINE_REGISTRY, inject_request_classes
from .utils import Network
from .utils.render_card import ResultCardRenderer
from .utils.types import FileContent

inject_request_classes()  # 注入请求类到注册表

ENGINE_MAP: dict[str, type] = {
    name: def_.req_class
    for name, def_ in ENGINE_REGISTRY.items()
    if def_.req_class is not None
}


class BaseSearchModel:
    """
    图像反向搜索基础模型类

    提供多种搜索引擎的统一接口，支持本地文件和URL搜索，
    可以输出文本结果或生成可视化图像结果，支持GIF格式自动转换
    """

    def __init__(
        self,
        proxies: str | None = None,
        cookies: dict | None = None,
        timeout: int = 60,
        default_params: dict | None = None,
        default_cookies: dict | None = None,
    ):
        """
        初始化搜索模型

        参数:
            proxies: 代理服务器配置
            cookies: Cookie配置
            timeout: 请求超时时间(秒)
            default_params: 各引擎的默认参数
            default_cookies: 各引擎的默认Cookie
        """
        self.proxies = proxies
        self.cookies = cookies
        self.timeout = timeout
        self.default_params = default_params or {}
        self.default_cookies = default_cookies or {}
        self._yandex_cookie = None
        self._yandex_cookie_timestamp = 0

    def _prepare_engine_params(self, api: str, search_params: dict) -> dict:
        """从搜索参数中提取引擎专属配置。

        每个引擎有各自的特殊参数（如 saucenao 的 dbmask、ehentai 的 is_ex），
        本方法将它们从 search_params 中 pop 出来，组装为引擎构造参数。

        参数:
            api: 搜索引擎名
            search_params: 合并了默认参数+kwargs 的搜索参数字典 (会被修改)

        返回:
            dict: 引擎专属参数字典，用于传递给引擎类的 __init__
        """
        engine_params = {}

        if api == "ascii2d":
            engine_params = {}

        if api == "animetrace":
            engine_params = {
                "is_multi": search_params.pop("is_multi", None),
                "ai_detect": search_params.pop("ai_detect", None),
            }
        elif api == "ehentai":
            engine_params = {
                "is_ex": search_params.pop("is_ex", False),
                "covers": search_params.pop("covers", False),
                "similar": search_params.pop("similar", True),
                "exp": search_params.pop("exp", False),
                "cookies": search_params.pop("cookies", None),
            }
        elif api == "saucenao":
            engine_params = {
                "api_key": search_params.pop("api_key", None),
                "hide": search_params.pop("hide", 3),
                "numres": search_params.pop("numres", 5),
                "minsim": search_params.pop("minsim", 30),
                "output_type": search_params.pop("output_type", 2),
                "testmode": search_params.pop("testmode", 0),
                "dbmask": search_params.pop("dbmask", None),
                "dbmaski": search_params.pop("dbmaski", None),
                "db": search_params.pop("db", 999),
                "dbs": search_params.pop("dbs", None),
            }
        elif api == "google":
            # API key 优先取顶层字段，兼容嵌套 api_keys dict
            serpapi_key = search_params.get("serpapi_key")
            zenserp_key = search_params.get("zenserp_key")

            if not serpapi_key and not zenserp_key:
                api_keys = search_params.get("api_keys", {})
                serpapi_key = api_keys.get("serpapi")
                zenserp_key = api_keys.get("zenserp")

            engine_params = {
                "serpapi_key": serpapi_key,
                "zenserp_key": zenserp_key,
                "country": search_params.get("country", "HK"),
                "hl": search_params.get("hl", "zh-CN"),
                "max_results": search_params.get("max_results", 10),
            }
        elif api == "yandex":
            engine_params = {
                "max_results": search_params.get("max_results", 10),
                "use_ru_fallback": search_params.get("use_ru_fallback", True),
            }

        return engine_params

    async def _check_yandex_cookie(self, cookie: dict) -> bool:
        """
        验证 Yandex Cookie 是否有效 (尝试访问主页)
        """
        if not cookie:
            return False
        try:
            # 简单 HEAD 请求或 GET 请求，检查是否返回 200 且无 CAPTCHA
            async with Network(
                cookies=cookie, proxies=self.proxies, timeout=10
            ) as client:
                resp = await client.get("https://yandex.com/images/")
                if resp.status_code == 200 and "captcha" not in resp.text.lower():
                    return True
        except Exception:
            pass
        return False

    async def _get_yandex_cookie(self):
        # Automated cookie fetching removed.
        # Fallback to manual default cookie if provided.
        return self.default_cookies.get("yandex")

    def _is_gif(self, file: FileContent) -> bool:
        """
        检查文件是否为GIF格式

        参数:
            file: 待检查的文件内容

        返回:
            bool: 如果是GIF格式返回True，否则返回False
        """
        if isinstance(file, (str, Path)):
            return str(file).lower().endswith(".gif")
        elif isinstance(file, bytes):
            return file.startswith((b"GIF87a", b"GIF89a"))
        return False

    async def _convert_gif_to_jpeg(self, file: FileContent) -> bytes:
        """
        将GIF图像转换为JPEG格式（异步方法，在单独线程中执行）

        参数:
            file: GIF格式的文件内容

        返回:
            bytes: 转换后的JPEG格式图像数据
        """

        def convert_image():
            if isinstance(file, bytes):
                img_data = file
            else:
                with open(file, "rb") as f:
                    img_data = f.read()
            img = Image.open(io.BytesIO(img_data))
            img.seek(0)
            jpeg_io = io.BytesIO()
            img.convert("RGB").save(jpeg_io, "JPEG", quality=85)
            return jpeg_io.getvalue()

        return await asyncio.to_thread(convert_image)

    async def search(
        self,
        api: str,
        file: FileContent = None,
        url: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        """
        执行图像反向搜索

        参数:
            api: 搜索引擎API名称
            file: 本地文件内容
            url: 图像URL
            **kwargs: 其他搜索参数

        返回:
            Optional[str]: 搜索结果文本，搜索失败时返回None

        异常:
            ValueError: 当API不支持或参数错误时抛出
        """
        if api not in ENGINE_MAP:
            available = ", ".join(ENGINE_MAP.keys())
            raise ValueError(f"不支持的引擎: {api}，支持的引擎: {available}")
        if not file and not url:
            raise ValueError("必须提供 file 或 url 参数")
        if file and url:
            raise ValueError("file 和 url 参数不能同时提供")
        if file and not url and self._is_gif(file):
            file = await self._convert_gif_to_jpeg(file)

        response = await self._search_engine(api, file=file, url=url, **kwargs)
        return response.show_result()

    async def _search_engine(
        self,
        api: str,
        file: FileContent = None,
        url: str | None = None,
        **kwargs: Any,
    ):
        """执行搜索并返回完整的引擎响应对象。

        管道流程:
            1. 获取引擎类 & 合并默认参数 + kwargs
            2. 按引擎类型提取引擎专属参数 (如 saucenao 的 dbmask)
            3. 解析 Cookie (yandex 动态获取 / ehentai 从参数取 / 全局默认)
            4. base64 → bytes 转换 (animetrace 除外，它直接接受 base64)
            5. 创建 Network 会话 → 实例化引擎 → 执行搜索

        返回:
            BaseSearchResponse: 引擎返回的完整响应对象
        """
        engine_class = ENGINE_MAP[api]
        # 合并默认参数：default_params < kwargs，后者覆盖前者
        default_params = self.default_params.get(api, {})
        search_params = {**default_params, **kwargs}
        # 提取引擎专属参数 (api_key, dbmask 等)，从 search_params 中弹出
        engine_params = self._prepare_engine_params(api, dict(search_params))

        # ── Cookie 解析 ──
        network_kwargs = {}
        if self.proxies:
            network_kwargs["proxies"] = self.proxies
        effective_cookies = None
        if api == "yandex":
            effective_cookies = await self._get_yandex_cookie()
        elif api == "ehentai" and "cookies" in search_params:
            effective_cookies = search_params.get("cookies")
        elif api in self.default_cookies:
            effective_cookies = self.default_cookies.get(api)
        elif self.cookies:
            effective_cookies = self.cookies
        if effective_cookies:
            network_kwargs["cookies"] = effective_cookies
        if self.timeout:
            network_kwargs["timeout"] = self.timeout

        # base64 → bytes: animetrace 原生支持 base64，其他引擎需要解码为 bytes
        if search_params.get("base64") and api != "animetrace":
            file = base64.b64decode(search_params.pop("base64"))

        async with Network(**network_kwargs) as network:
            engine_instance = engine_class(network=network, **engine_params)
            # animetrace 特殊路径：传 base64 + model 参数
            if api == "animetrace" and search_params.get("base64"):
                response = await engine_instance.search(
                    base64=search_params.pop("base64"),
                    model=search_params.pop("model", None),
                    **search_params,
                )
            else:
                response = await engine_instance.search(
                    file=file, url=url, **search_params
                )
            return response

    async def search_and_print(
        self,
        api: str,
        file: FileContent = None,
        url: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        执行搜索并打印结果到控制台

        参数:
            api: 搜索引擎API名称
            file: 本地文件内容
            url: 图像URL
            **kwargs: 其他搜索参数

        返回:
            None
        """
        try:
            result = await self.search(api=api, file=file, url=url, **kwargs)
            print(result)
        except Exception:
            print(f"❌ {api} 搜索失败")

    async def search_and_draw(
        self,
        api: str,
        file: FileContent = None,
        url: str | None = None,
        **kwargs: Any,
    ) -> Image.Image:
        """
        执行搜索并将结果渲染为图像

        参数:
            api: 搜索引擎API名称
            file: 本地文件内容
            url: 图像URL
            **kwargs: 其他搜索参数

        返回:
            Image.Image: 渲染后的结果图像
        """
        try:
            response = await self._search_engine(api=api, file=file, url=url, **kwargs)
            raw_items = getattr(response, "raw", []) or []
            items = self._build_items_from_raw(raw_items)

            # 下载缩略图
            network_kwargs = {}
            if self.proxies:
                network_kwargs["proxies"] = self.proxies
            if self.timeout:
                network_kwargs["timeout"] = self.timeout

            async def download_all_thumbs():
                async with Network(**network_kwargs) as client:
                    tasks = []
                    for item in items:
                        url = item.get("thumbnail_url", "")
                        if url:
                            tasks.append(self._download_thumbnail(client, url))
                        else:
                            tasks.append(None)
                    results = []
                    for t in tasks:
                        if t is not None:
                            results.append(await t)
                        else:
                            results.append(None)
                    return results

            thumb_images = await download_all_thumbs()
            for i, thumb in enumerate(thumb_images):
                if i < len(items):
                    items[i]["thumbnail_image"] = thumb

            source_image = None

            def load_image():
                if file is not None:
                    if isinstance(file, (str, Path)):
                        return Image.open(file)
                    elif isinstance(file, bytes):
                        return Image.open(io.BytesIO(file))
                return None

            if file is not None:
                source_image = await asyncio.to_thread(load_image)
            elif url is not None:
                async with Network(**network_kwargs) as client:
                    resp = await client.download(url)

                    def load_from_url_bytes(d: bytes):
                        return Image.open(io.BytesIO(d))

                    source_image = await asyncio.to_thread(load_from_url_bytes, resp)

            # AnimeTrace: 提取 AI 检测结果
            ai_detect = getattr(response, "ai", None)
            return await asyncio.to_thread(
                self.draw_results, api, items, source_image, ai_detect=ai_detect
            )
        except Exception:
            return await asyncio.to_thread(self.draw_error, api, "搜索失败")

    def _format_error(self, api: str, error_msg: str) -> str:
        """
        格式化错误信息

        参数:
            api: 搜索引擎API名称
            error_msg: 原始错误信息

        返回:
            str: 格式化后的错误信息
        """
        friendly_msg = (
            "未搜索到相关信息"
            if "list index out of range" in error_msg.lower()
            else error_msg
        )
        return f"""{"=" * 50}
{api.upper()} 搜索失败
{"=" * 50}
错误信息: {friendly_msg}
{"=" * 50}"""

    @classmethod
    def get_supported_engines(cls) -> list[str]:
        """
        获取所有支持的搜索引擎列表

        返回:
            list[str]: 支持的搜索引擎名称列表
        """
        return list(ENGINE_MAP.keys())

    def draw_results(
        self,
        api: str,
        items: list[dict],
        source_image: Image.Image | None = None,
        ai_detect: bool | None = None,
    ) -> Image.Image:
        """绘制搜索结果图像（使用新卡片样式）"""
        try:
            renderer = ResultCardRenderer()
            return renderer.render(api, items, source_image, ai_detect=ai_detect)
        except Exception:
            return self._draw_results_legacy(api, "渲染失败", source_image)

    def _build_items_from_raw(self, raw_items: list) -> list[dict]:
        """将引擎返回的原始解析结果转为统一的卡片数据结构。

        特殊处理:
            - AnimeTrace: 按角色拆分，每个角色一张卡片 (最多 10 张)
            - 其他引擎: 提取 title/url/similarity/source/author/thumbnail

        参数:
            raw_items: 引擎返回的解析后对象列表

        返回:
            list[dict]: 结构化字典列表，供 render_card 使用
        """
        items = []
        for item in raw_items[:5]:
            # AnimeTrace: 一个结果可能含多个角色，逐个展开
            if hasattr(item, "characters") and hasattr(item, "box"):
                for c in item.characters:
                    if len(items) >= 10:
                        break
                    items.append(
                        {
                            "title": f"角色: {c.name}",
                            "url": "",
                            "similarity": "",
                            "source": f"作品: {c.work}" if c.work else "AnimeTrace",
                            "author": "",
                            "thumbnail_url": "",
                        }
                    )
                if len(items) >= 10:
                    break
            else:
                sim = getattr(item, "similarity", 0)
                items.append(
                    {
                        "title": getattr(item, "title", "") or "",
                        "url": getattr(item, "url", "") or "",
                        "similarity": self._format_similarity(sim),
                        "source": getattr(item, "source", "")
                        or getattr(item, "index_name", "")
                        or "",
                        "author": getattr(item, "author", "") or "",
                        "thumbnail_url": getattr(item, "thumbnail", "") or "",
                    }
                )
        return items

    @staticmethod
    def _format_similarity(sim) -> str:
        """将相似度数值格式化为字符串"""
        if isinstance(sim, (int, float)):
            if sim > 0:
                return f"{sim:.1f}%"
        return str(sim) if sim else ""

    async def _download_thumbnail(
        self, client: Network, url: str
    ) -> Image.Image | None:
        """
        异步下载缩略图并返回 PIL Image

        参数:
            client: Network 客户端实例
            url: 缩略图 URL

        返回:
            Optional[Image.Image]: 下载的缩略图，失败时返回 None
        """
        if not url:
            return None
        try:
            data = await client.download(url)
            if data:

                def load_from_bytes(d: bytes):
                    return Image.open(io.BytesIO(d))

                return await asyncio.to_thread(load_from_bytes, data)
        except Exception:
            pass
        return None

    def _draw_results_legacy(
        self, api: str, result: str | list, source_image: Image.Image | None = None
    ) -> Image.Image:
        """旧版文字渲染（回退用）"""
        margin = 20
        if isinstance(result, list):
            text_lines = []
            for item in result:
                parts = [
                    f"标题: {item.get('title', '')}",
                    f"来源: {item.get('source', '')}",
                ]
                if item.get("similarity"):
                    parts.append(f"相似度: {item['similarity']}")
                text_lines.append(" | ".join(parts))
                text_lines.append(item.get("url", ""))
                text_lines.append("---")
            result = "\n".join(text_lines)
        lines = result.split("\n")
        base_dir = Path(__file__).parent
        font_path = str(base_dir / "resource/font/arialuni.ttf")
        try:
            font = ImageFont.truetype(font_path, 18)
            title_font = ImageFont.truetype(font_path, 24)
        except OSError:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()
        title_text = f"{api.upper()} search results"
        if hasattr(title_font, "getbbox"):
            title_width = title_font.getbbox(title_text)[2] + margin * 2
        else:
            title_width = title_font.getsize(title_text)[0] + margin * 2
        max_text_width = 0
        for line in lines:
            if hasattr(font, "getbbox"):
                line_width = font.getbbox(line)[2] + margin * 2
            else:
                line_width = font.getsize(line)[0] + margin * 2
            max_text_width = max(max_text_width, line_width)
        source_img_height = 0
        source_img_width = 0
        if source_image:
            max_source_width = 800
            orig_width, orig_height = source_image.size
            if orig_width > max_source_width:
                ratio = max_source_width / orig_width
                source_img_width = max_source_width
                source_img_height = int(orig_height * ratio)
                source_image = source_image.resize(
                    (source_img_width, source_img_height), Image.LANCZOS
                )
            else:
                source_img_width = orig_width
                source_img_height = orig_height
        width = max(800, title_width, max_text_width, source_img_width + margin * 2)
        if hasattr(font, "getbbox"):
            line_height = max(25, font.getbbox("Ay")[3] + 7)
        else:
            line_height = max(25, font.getsize("Ay")[1] + 7)
        header_height = 60
        content_height = margin + line_height * len(lines)
        source_area_height = source_img_height + margin * 2 if source_image else 0
        total_height = header_height + content_height + source_area_height
        img = Image.new("RGB", (width, total_height), color="white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (width, header_height)], fill="#4a6ea9")
        draw.text((margin, margin), title_text, font=title_font, fill="white")
        y_offset = header_height
        if source_image:
            x_center = (width - source_img_width) // 2
            img.paste(source_image, (x_center, y_offset + margin))
            y_offset += source_img_height + margin * 2
            draw.line(
                [
                    (margin, y_offset - margin // 2),
                    (width - margin, y_offset - margin // 2),
                ],
                fill="#cccccc",
                width=2,
            )
        y_position = y_offset
        for line in lines:
            if line.startswith("="):
                draw.line(
                    [(margin, y_position), (width - margin, y_position)],
                    fill="#cccccc",
                    width=1,
                )
            else:
                draw.text((margin, y_position), line, font=font, fill="black")
            y_position += line_height
        return img

    def draw_error(self, api: str, error_msg: str) -> Image.Image:
        """绘制错误图像（使用卡片样式）"""
        try:
            renderer = ResultCardRenderer()
            return renderer.render_error(api, error_msg)
        except Exception:
            pass
        # fallback
        width, height = 600, 200
        img = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (width, 60)], fill="#e74c3c")
        try:
            base_dir = Path(__file__).parent
            font_path = str(base_dir / "resource/font/arialuni.ttf")
            font = ImageFont.truetype(font_path, 18)
            title_font = ImageFont.truetype(font_path, 24)
        except OSError:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()
        margin = 20
        draw.text(
            (margin, margin),
            f"{api.upper()} search failed",
            font=title_font,
            fill="white",
        )
        draw.text((margin, 80), f"Error: {error_msg}", font=font, fill="black")
        return img
