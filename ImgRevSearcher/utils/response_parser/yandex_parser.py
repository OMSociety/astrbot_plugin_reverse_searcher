import json
from typing import Any, Dict, List
from pyquery import PyQuery
from typing_extensions import override
from .base_parser import BaseSearchResponse

class YandexResponse(BaseSearchResponse):
    """
    Yandex 搜索结果解析类
    """
    def __init__(self, resp_data: str, resp_url: str, **kwargs: Any):
        super().__init__(resp_data, resp_url, **kwargs)
        self.max_results = kwargs.get("max_results", 10)

    @override
    def _parse_response(self, resp_data: str, **kwargs: Any) -> None:
        dom = PyQuery(resp_data)
        # ... (rest is same) ...
        self.raw = []
        
        # Yandex 结果通常存储在 div.Root 的 data-state 属性中 (JSON)
        # Upstream logic:
        # data_div = data.find('div.Root[id^="ImagesApp-"]')
        # data_state = data_div.attr("data-state")
        
        data_div = dom('div.Root[id^="ImagesApp-"]')
        data_state = data_div.attr("data-state")
        
        if not data_state:
            return

        try:
            data_json = json.loads(data_state)
            
            # 路径: initialState.cbirSites.sites
            # 使用简单的 dict.get 链式获取，避免深度依赖
            initial_state = data_json.get("initialState", {})
            cbir_sites = initial_state.get("cbirSites", {})
            sites = cbir_sites.get("sites", [])
            
            for site in sites:
                try:
                    url = site.get("url", "")
                    title = site.get("title", "")
                    content = site.get("description", "")
                    domain = site.get("domain", "")
                    
                    thumb_info = site.get("thumb", {})
                    thumb_url = thumb_info.get("url", "")
                    if thumb_url and thumb_url.startswith("//"):
                        thumb_url = "https:" + thumb_url
                    
                    original_image = site.get("originalImage", {})
                    width = original_image.get("width", 0)
                    height = original_image.get("height", 0)
                    size_str = f"{width}x{height}"
                    
                    self.raw.append({
                        "title": title,
                        "url": url,
                        "thumbnail": thumb_url,
                        "author": domain, # 使用域名作为来源/作者
                        "other_info": f"{size_str} {content[:50]}...",
                    })
                except:
                    continue
        except json.JSONDecodeError:
            pass

    @override
    def show_result(self) -> str:
        if not self.raw:
            return "Yandex 未找到相关结果"
            
        return "\n".join([
            f"标题: {item['title']}\n"
            f"来源: {item['author']}\n"
            f"链接: {item['url']}\n"
            f"信息: {item['other_info']}\n"
            f"{'-'*30}"
            for item in self.raw[:self.max_results]
        ])
