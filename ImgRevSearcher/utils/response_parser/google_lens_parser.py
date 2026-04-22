
import json
from typing import Any, Optional
from pyquery import PyQuery
from typing_extensions import override
from .base_parser import BaseResParser, BaseSearchResponse

class GoogleLensItem(BaseResParser):
    def __init__(self, title: str, url: str, thumbnail: str = "", source: str = "", group: str = "visual"):
        super().__init__(None)
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.source = source
        self.group = group # 'ai', 'exact', 'visual' (SerpApi) or 'pages', 'organic' (Zenserp)

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

        # Auto-detect engine based on JSON structure
        if "visual_matches" in data or "knowledge_graph" in data or "search_metadata" in data:
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
            for match in data["exact_matches"]:
                 self._add_serpapi_item(match, group="exact")
        
        # 3. Visual Matches
        if "visual_matches" in data:
            for match in data["visual_matches"]:
                group = "exact" if match.get("exact_match") else "visual"
                self._add_serpapi_item(match, group=group)

        # 4. Knowledge Graph
        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            title = kg.get("title") or kg.get("header_images", [{}])[0].get("title") or "Knowledge Graph"
            url = kg.get("link") or kg.get("website") or ""
            thumb = kg.get("header_images", [{}])[0].get("image") or ""
            desc = kg.get("description") or ""
            
            if title and (url or desc):
                if not url: url = "#"
                item = GoogleLensItem(title=title, url=url, thumbnail=thumb, source="Knowledge Graph", group="ai")
                self.raw.append(item)
                if desc and not self.ai_overview:
                    self.ai_overview = desc

    def _parse_zenserp(self, data: dict):
        if "reverse_image_results" not in data:
            return
            
        res = data["reverse_image_results"]
        
        # Priority 1: Organic (High quality, titles enabled)
        if "organic" in res:
            for match in res["organic"]:
                self._add_zenserp_item(match, original_group="organic")
        
        # Priority 2: Pages with matching images
        if "pages_with_matching_images" in res:
            for match in res["pages_with_matching_images"]:
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

        title = (_get("title") or 
                _get("source") or 
                _get("snippet") or 
                _get("text") or 
                _get("description") or 
                _get("subtitle") or
                "Visual Search Result") # Final Fallback

        url = (_get("link") or 
              _get("source_url") or 
              _get("page_url") or 
              _get("url") or 
              _get("website") or
              "")

        # If url is missing but we have thumbnail, it's still a valid visual result
        if not url and group == "visual":
             url = _get("image") or _get("thumbnail") # Fallback to image itself if no page link

        item = GoogleLensItem(
            title=title,
            url=url,
            thumbnail=_get("thumbnail"),
            source=_get("source"),
            group=group
        )
        self.raw.append(item)

    def _add_zenserp_item(self, match: dict, original_group: str):
        # Determine internal group for display
        group = "pages" if original_group in ("organic", "pages") else "visual"
        
        # Helper for safer string conversion
        def _s(val):
            return str(val).strip() if val else ""

        title = _s(match.get("title")) or _s(match.get("source")) or _s(match.get("domain")) or "Visual Search Result"
        url = _s(match.get("url")) or _s(match.get("link")) or _s(match.get("destination"))
        
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
                from urllib.parse import urlparse
                source = urlparse(url).netloc.replace("www.", "")
            except:
                pass

        item = GoogleLensItem(
            title=title,
            url=url,
            thumbnail=_s(match.get("thumbnail")),
            source=source,
            group=group
        )
        self.raw.append(item)
        
    def show_result(self) -> Optional[str]:
        if not self.raw and not self.ai_overview:
             # Return debug info if available
             return getattr(self, "debug_info", "Google Lens: 未找到结果且无调试信息") or None
        
        lines = ["Google Lens Result:", "-" * 40]
        # ... (rest same) ...
        
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
                if item.source: lines.append(f"   来源: {item.source}")
                lines.append(f"   链接: {item.url}")
            lines.append("-" * 40)
            
        if visual_items:
            lines.append("【相似结果】:")
            for idx, item in enumerate(visual_items[:limit], 1):
                lines.append(f"{idx}. {item.title}")
                if item.source: lines.append(f"   来源: {item.source}")
                lines.append(f"   链接: {item.url}")
                
        return "\n".join(lines)
