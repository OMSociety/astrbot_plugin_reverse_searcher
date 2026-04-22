from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union
from pathlib import Path


class DomainTag(str, Enum):
    """
    域名标签枚举类
    
    用于标记搜索结果中的域名类型
    """
    STOCK = "stock"
    COLLECTION = "collection"


class SearchType(str, Enum):
    """
    搜索类型枚举类
    
    定义不同的搜索模式和范围
    """
    ALL = "all"
    PRODUCTS = "products" 
    VISUAL_MATCHES = "visual_matches"
    EXACT_MATCHES = "exact_matches"


# 类型别名定义
FilePath = Union[str, Path]
FileContent = Union[str, bytes, FilePath, None]


@dataclass
class DomainInfo:
    """
    域名信息数据类
    
    存储搜索结果中域名的相关信息，包括域名名称、计数和标签
    """
    domain: str
    count: int
    tag: Optional[DomainTag] = None

    @classmethod
    def from_raw_data(cls, data: list[Any]) -> "DomainInfo":
        """
        从原始数据创建域名信息对象
        
        参数:
            data: 包含域名信息的原始数据列表
            
        返回:
            DomainInfo: 创建的域名信息对象
        """
        domain_name = str(data[0])
        count = int(data[1])
        tag = DomainTag(data[2][0]) if data[2] else None
        return cls(domain=domain_name, count=count, tag=tag)
