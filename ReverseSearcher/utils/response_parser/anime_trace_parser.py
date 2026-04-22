from typing import Any, Optional, NamedTuple
from typing_extensions import override
from .base_parser import BaseResParser, BaseSearchResponse


class Character(NamedTuple):
    """
    角色信息命名元组
    
    存储识别出的动漫角色名称和作品名
    """
    name: str
    work: str


class AnimeTraceItem(BaseResParser):
    """
    AnimeTrace搜索结果项解析器
    
    解析单个识别结果，包含角色信息和位置框
    """
    
    def __init__(self, data: dict[str, Any], **kwargs: Any):
        """
        初始化AnimeTrace结果项解析器
        
        参数:
            data: 原始结果数据
            **kwargs: 其他解析参数
        """
        super().__init__(data, **kwargs)

    @override
    def _parse_data(self, data: dict[str, Any], **kwargs: Any) -> None:
        """
        解析AnimeTrace结果数据
        
        参数:
            data: 原始结果数据
            **kwargs: 其他解析参数
        """
        self.box: list[float] = data["box"]
        self.box_id: str = data["box_id"]
        character_data = data["character"]
        self.characters: list[Character] = []
        for char_info in character_data:
            character = Character(char_info["character"], char_info["work"])
            self.characters.append(character)


class AnimeTraceResponse(BaseSearchResponse[AnimeTraceItem]):
    """
    AnimeTrace搜索响应解析器
    
    解析完整的AnimeTrace API响应，包含多个识别结果
    """
    
    def __init__(self, resp_data: dict[str, Any], resp_url: str, **kwargs: Any) -> None:
        """
        初始化AnimeTrace响应解析器
        
        参数:
            resp_data: 原始响应数据
            resp_url: 响应URL
            **kwargs: 其他解析参数
        """
        super().__init__(resp_data, resp_url, **kwargs)

    @override
    def _parse_response(self, resp_data: dict[str, Any], **kwargs: Any) -> None:
        """
        解析AnimeTrace响应数据
        
        参数:
            resp_data: 原始响应数据
            **kwargs: 其他解析参数
        """
        self.code: int = resp_data["code"]
        self.ai: bool = resp_data.get("ai", False)
        self.trace_id: str = resp_data["trace_id"]
        results = resp_data["data"]
        self.raw: list[AnimeTraceItem] = [AnimeTraceItem(item) for item in results]
        
    def show_result(self) -> Optional[str]:
        """
        生成可读的搜索结果文本
        
        返回:
            str: 格式化的搜索结果文本
        """
        has_characters = False
        if self.raw:
            for item in self.raw:
                if item.characters:
                    has_characters = True
                    break
        if not has_characters:
            return None
        lines = [f"是否为 AI 生成: {'是' if self.ai else '否'}", "-" * 50]
        if self.raw:
            for _, item in enumerate(self.raw, 1):
                if characters := item.characters:
                    for j, character in enumerate(characters, 1):
                        lines.append(f"结果 #{j}")
                        lines.append(f"作品名: {character.work}")
                        lines.append(f"角色名: {character.name}")
                        lines.append("-" * 50)
        return "\n".join(lines)
