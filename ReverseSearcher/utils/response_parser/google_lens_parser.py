import json
import logging
from typing import Any, Iterator
from urllib.parse import urlparse

from typing_extensions import override

from .base_parser import BaseResParser, BaseSearchResponse

logger = logging.getLogger(__name__)


def _iter_dict_items(container) -> Iterator[dict]:
    """逐个产出结果项，容器或单条形态异常时跳过而不中断整批

    容器必须是 list（JSON 数组），且只产出 dict 条目：
    容器为 null / 字符串 / 字典，或单条为 null / 字符串等，都只影响该批/该条，
    不得让异常逃逸导致已解析的 ai_overview 与 visual_matches 一起丢失。
    """
    if not isinstance(container, list):
        return
    for item in container:
        if isinstance(item, dict):
            yield item


class GoogleLensItem(BaseResParser):
    def __init__(
        self,
        title: str,
        url: str,
        thumbnail: str = "",
        source: str = "",
        group: str = "visual",
    ):
        super().__init__(None)
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.source = source
        self.group = (
            group  # 'ai', 'exact', 'visual' (SerpApi) or 'pages', 'organic' (Zenserp)
        )

    @override
    def _parse_data(self, data: Any, **kwargs: Any) -> None:
        pass


class GoogleLensResponse(BaseSearchResponse[GoogleLensItem]):
    def __init__(self, resp_data: str, resp_url: str, **kwargs: Any):
        super().__init__(resp_data, resp_url, **kwargs)
        self.max_results = kwargs.get("max_results", 10)

    def _parse_response(self, resp_data: str, **kwargs: Any) -> None:
        self.ai_overview = ""
        self.raw: list[GoogleLensItem] = []
        try:
            data = json.loads(resp_data)
        except json.JSONDecodeError:
            return

        # 入口守护：响应必须是 JSON 对象。list/str/number 一律走既有的“解析失败”兜底
        # （raw/ai_overview 保持空 + debug_info 记录），不进入引擎分派——
        # 否则既会在分派时按字符串/下标误判，也会让下面兜底那行 list(data.keys()) 自己抛错。
        # 文案点明“未切换备引擎”：本层就地降级，不会再由异常触发 GoogleLens.search 的备引擎切换。
        if not isinstance(data, dict):
            self.debug_info = (
                f"解析失败，响应类型: {type(data).__name__}（未切换备引擎）"
            )
            return

        # Auto-detect engine based on JSON structure
        if (
            "visual_matches" in data
            or "knowledge_graph" in data
            or "search_metadata" in data
        ):
            self._parse_serpapi(data)
        elif "reverse_image_results" in data or "zenserp" in self.url:
            self._parse_zenserp(data)

        # Fallback debug info
        if not self.raw and not self.ai_overview:
            self.debug_info = f"解析失败，响应键值: {list(data.keys())}"
            if "error" in data:
                self.debug_info += f"\nAPI错误: {data['error']}"
        else:
            self.debug_info = ""

    def _parse_serpapi(self, data: dict):
        # 1. AI Overview
        if "ai_overview" in data:
            ai_data = data["ai_overview"]
            if isinstance(ai_data, str):
                self.ai_overview = ai_data
            elif isinstance(ai_data, dict):
                # Check for actual content, skip if only token/link (which means "Searching...")
                text_content = ai_data.get("text") or ai_data.get("snippet")
                if text_content:
                    self.ai_overview = text_content

        # 2. Exact Matches
        if "exact_matches" in data:
            for match in _iter_dict_items(data["exact_matches"]):
                self._add_serpapi_item(match, group="exact")

        # 3. Visual Matches
        if "visual_matches" in data:
            for match in _iter_dict_items(data["visual_matches"]):
                group = "exact" if match.get("exact_match") else "visual"
                self._add_serpapi_item(match, group=group)

        # 4. Knowledge Graph
        # 单条 KG 的结构异常（null / [] / header_images 元素非 dict 等）只跳过该条：
        # 本块之外已解析的 ai_overview / visual_matches 必须保留，
        # 否则异常会逃出 _parse_response（只吞 JSONDecodeError）并整批丢弃、降级 Zenserp。
        if "knowledge_graph" in data:
            try:
                kg = data["knowledge_graph"]
                if isinstance(kg, dict):
                    self._append_knowledge_graph(kg)
            except Exception as exc:  # noqa: BLE001 - 单条 KG 容错，不影响整批
                # 容错本身要留痕：这里出真 bug 时只靠 debug_info 排查不到
                logger.debug(
                    f"[GoogleLens] Knowledge Graph 解析失败，已跳过该条: {exc}",
                    exc_info=True,
                )

    def _append_knowledge_graph(self, kg: dict):
        """追加单条 Knowledge Graph 结果项

        header_images 缺失 / [] / None / 首元素非 dict 一律降级为空 dict：
        .get 的默认值只在键缺失时生效，直接取 [0] 会 IndexError/TypeError/AttributeError。
        """
        header_images = kg.get("header_images")
        header = (
            header_images[0]
            if isinstance(header_images, list) and header_images
            else None
        )
        if not isinstance(header, dict):
            header = {}

        title = kg.get("title") or header.get("title") or "Knowledge Graph"
        url = kg.get("link") or kg.get("website") or ""
        thumb = header.get("image") or ""
        desc = kg.get("description") or ""

        if title and (url or desc):
            if not url:
                url = "#"
            item = GoogleLensItem(
                title=title,
                url=url,
                thumbnail=thumb,
                source="Knowledge Graph",
                group="ai",
            )
            self.raw.append(item)
            if desc and not self.ai_overview:
                self.ai_overview = desc

    def _parse_zenserp(self, data: dict):
        if "reverse_image_results" not in data:
            return

        res = data["reverse_image_results"]
        # 单条/整批形态异常（reverse_image_results 为 null 等）只跳过整个备引擎解析，
        # 不得让异常逃逸（上一级是 GoogleLens.search 的降级 except）。
        if not isinstance(res, dict):
            return

        # Priority 1: Organic (High quality, titles enabled)
        if "organic" in res:
            for match in _iter_dict_items(res["organic"]):
                self._add_zenserp_item(match, original_group="organic")

        # Priority 2: Pages with matching images
        if "pages_with_matching_images" in res:
            for match in _iter_dict_items(res["pages_with_matching_images"]):
                self._add_zenserp_item(match, original_group="pages")

        # Priority 3: Similar Images (Visual matches, often no title)
        # User Feedback: Zenserp similar_images often contain invalid links (redirect to lens home), so we skip them.
        # if "similar_images" in res:
        #      for match in res["similar_images"]:
        #          self._add_zenserp_item(match, original_group="visual")

    def _add_serpapi_item(self, match: dict, group: str):
        # Helper to get stripped string
        def _get(key):
            val = match.get(key)
            return str(val).strip() if val else ""

        title = (
            _get("title")
            or _get("source")
            or _get("snippet")
            or _get("text")
            or _get("description")
            or _get("subtitle")
            or "Visual Search Result"
        )  # Final Fallback

        url = (
            _get("link")
            or _get("source_url")
            or _get("page_url")
            or _get("url")
            or _get("website")
            or ""
        )

        # If url is missing but we have thumbnail, it's still a valid visual result
        if not url and group == "visual":
            url = _get("image") or _get(
                "thumbnail"
            )  # Fallback to image itself if no page link

        item = GoogleLensItem(
            title=title,
            url=url,
            thumbnail=_get("thumbnail"),
            source=_get("source"),
            group=group,
        )
        self.raw.append(item)

    def _add_zenserp_item(self, match: dict, original_group: str):
        # Determine internal group for display
        group = "pages" if original_group in ("organic", "pages") else "visual"

        # Helper for safer string conversion
        def _s(val):
            return str(val).strip() if val else ""

        title = (
            _s(match.get("title"))
            or _s(match.get("source"))
            or _s(match.get("domain"))
            or "Visual Search Result"
        )
        url = (
            _s(match.get("url"))
            or _s(match.get("link"))
            or _s(match.get("destination"))
        )

        # If url is missing, try image url as fallback
        if not url:
            url = _s(match.get("image")) or _s(match.get("thumbnail"))

        # Fallback for similar images title
        if group == "visual" and title == "Visual Search Result":
            title = "Similar Image"

        # Attempt to extract source from URL if missing
        source = _s(match.get("source")) or _s(match.get("destination"))
        if not source and url.startswith("http"):
            try:
                source = urlparse(url).netloc.replace("www.", "")
            except Exception:
                pass

        item = GoogleLensItem(
            title=title,
            url=url,
            thumbnail=_s(match.get("thumbnail")),
            source=source,
            group=group,
        )
        self.raw.append(item)

    def show_result(self) -> str | None:
        if not self.raw and not self.ai_overview:
            # Return debug info if available
            return (
                getattr(self, "debug_info", "Google Lens: 未找到结果且无调试信息")
                or None
            )

        lines = ["Google Lens Result:", "-" * 40]

        if self.ai_overview:
            lines.append(f"[AI 摘要]:\n{self.ai_overview}")
            lines.append("-" * 40)

        # Group items
        exact_items = [i for i in self.raw if i.group in ("exact", "pages")]
        visual_items = [i for i in self.raw if i.group in ("visual", "organic")]

        limit = self.max_results

        if exact_items:
            lines.append("【包含图片的页面 / 精确匹配】:")
            for idx, item in enumerate(exact_items[:limit], 1):
                lines.append(f"{idx}. {item.title}")
                if item.source:
                    lines.append(f"   来源: {item.source}")
                lines.append(f"   链接: {item.url}")
            lines.append("-" * 40)

        if visual_items:
            lines.append("【相似结果】:")
            for idx, item in enumerate(visual_items[:limit], 1):
                lines.append(f"{idx}. {item.title}")
                if item.source:
                    lines.append(f"   来源: {item.source}")
                lines.append(f"   链接: {item.url}")

        return "\n".join(lines)
