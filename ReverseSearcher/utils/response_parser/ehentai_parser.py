from typing import Any, Optional
import json
from pathlib import Path
from pyquery import PyQuery
from typing_extensions import override
from ..ext_tools import parse_html
from .base_parser import BaseResParser, BaseSearchResponse


class EHentaiItem(BaseResParser):
    """
    E-Hentai搜索结果项解析器
    
    解析单个画廊结果，提取标题、URL、缩略图、类型、日期、页数和标签等信息
    """
    
    def __init__(self, data: PyQuery, **kwargs: Any):
        """
        初始化E-Hentai结果项解析器
        
        参数:
            data: 包含结果项HTML的PyQuery对象
            **kwargs: 其他解析参数
        """
        super().__init__(data, **kwargs)

    @override
    def _parse_data(self, data: PyQuery, **kwargs: Any) -> None:
        """
        解析E-Hentai结果数据
        
        参数:
            data: 包含结果项HTML的PyQuery对象
            **kwargs: 其他解析参数
        """
        self._arrange(data)

    def _arrange(self, data: PyQuery) -> None:
        """
        整理和提取E-Hentai结果项中的各项数据
        
        参数:
            data: 包含结果项HTML的PyQuery对象
        """
        glink = data.find(".glink")
        self.title: str = glink.text()
        if glink.parent("div"):
            self.url: str = glink.parent("div").parent("a").attr("href")
        else:
            self.url = glink.parent("a").attr("href")
        thumbnail = data.find(".glthumb img") or data.find(".gl1e img") or data.find(".gl3t img")
        self.thumbnail: str = thumbnail.attr("data-src") or thumbnail.attr("src")
        _type = data.find(".cs") or data.find(".cn")
        self.type: str = _type.eq(0).text() or ""
        self.date: str = data.find("[id^='posted']").eq(0).text() or ""
        self.pages: str = "解析失败"
        if glink and len(glink) > 0:
            try:
                tr_element = glink.parent().parent().parent()
                if len(tr_element) > 0:
                    pages_div = tr_element.find(".gl4c div").filter(
                        lambda i, e: "pages" in PyQuery(e).text()
                    )
                    if len(pages_div) > 0:
                        pages_text = pages_div.eq(0).text().strip()
                        self.pages = pages_text.split()[0] if pages_text else "解析失败"
            except Exception:
                pass
        self.tags: list[str] = []
        for i in data.find("div[class=gt],div[class=gtl]").items():
            if tag := i.attr("title"):
                self.tags.append(tag)


class EHentaiResponse(BaseSearchResponse[EHentaiItem]):
    """
    E-Hentai搜索响应解析器
    
    解析完整的E-Hentai搜索响应，包含多个画廊结果
    """
    
    def __init__(self, resp_data: str, resp_url: str, **kwargs: Any):
        """
        初始化E-Hentai响应解析器
        
        参数:
            resp_data: 原始HTML响应数据
            resp_url: 响应URL
            **kwargs: 其他解析参数
        """
        super().__init__(resp_data, resp_url, **kwargs)

    @override
    def _parse_response(self, resp_data: str, **kwargs: Any) -> None:
        """
        解析E-Hentai响应数据
        
        参数:
            resp_data: 原始HTML响应数据
            **kwargs: 其他解析参数
        """
        data = parse_html(resp_data)
        self.origin: PyQuery = data
        if "No unfiltered results" in resp_data:
            self.raw: list[EHentaiItem] = []
        elif tr_items := data.find(".itg").children("tr").items():
            self.raw = [EHentaiItem(i) for i in tr_items if i.children("td")]
        else:
            gl1t_items = data.find(".itg").children(".gl1t").items()
            self.raw = [EHentaiItem(i) for i in gl1t_items]
            
    def show_result(self, translations_file: str = "resource/translations/ehviewer_translations.json") -> Optional[str]:
        """
        生成可读的搜索结果文本
        
        支持使用翻译文件将标签翻译为本地语言
        
        参数:
            translations_file: 翻译文件路径
            
        返回:
            str: 格式化的搜索结果文本
        """
        try:
            base_dir = Path(__file__).parent.parent.parent
            abs_translations_file = base_dir / translations_file
            with open(abs_translations_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        except Exception:
            translations = {}
        has_valid_results = False
        if self.raw:
            for item in self.raw:
                if item.title or item.url or item.tags:
                    has_valid_results = True
                    break
        if not has_valid_results:
            return None
        categorized_tags = {}
        for tag in self.raw[0].tags:
            if ':' in tag:
                category, tag_name = tag.split(':', 1)
                category_cn = translations.get('rows', {}).get(category, category)
                tag_name_cn = tag_name
                if category in translations:
                    tag_name_cn = translations[category].get(tag_name, tag_name)
                if category_cn not in categorized_tags:
                    categorized_tags[category_cn] = []
                categorized_tags[category_cn].append(tag_name_cn)
        tag_lines = []
        for category, tags in categorized_tags.items():
            tag_line = f"{category}: {'; '.join(tags)}"
            tag_lines.append(tag_line)
        type_cn = translations.get('reclass', {}).get(self.raw[0].type.lower(), self.raw[0].type)
        lines = [f"结果 #1", f"链接: {self.raw[0].url}", f"上传时间: {self.raw[0].date}",
                f"标题: {self.raw[0].title}", f"类型: {type_cn}", f"页数: {self.raw[0].pages}", "标签:"]
        lines.extend([f"  {tag_line}" for tag_line in tag_lines])
        return "\n".join(lines)
