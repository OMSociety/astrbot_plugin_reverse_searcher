from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Optional

T = TypeVar("T")


class BaseResParser(ABC):
    """
    响应项解析基类
    
    解析单个搜索结果项的基类，提供通用的属性和解析接口
    """
    
    def __init__(self, data: Any, **kwargs: Any):
        """
        初始化响应项解析器
        
        参数:
            data: 原始响应数据
            **kwargs: 其他解析参数
        """
        self.origin: Any = data
        self.url: str = ""
        self.thumbnail: str = ""
        self.title: str = ""
        self.similarity: float = 0.0
        self._parse_data(data, **kwargs)

    @abstractmethod
    def _parse_data(self, data: Any, **kwargs: Any) -> None:
        """
        解析响应数据
        
        参数:
            data: 原始响应数据
            **kwargs: 其他解析参数
            
        异常:
            NotImplementedError: 子类必须实现此方法
        """
        pass


class BaseSearchResponse(ABC, Generic[T]):
    """
    搜索响应基类
    
    解析完整搜索响应的基类，包含多个搜索结果项
    """
    
    def __init__(self, resp_data: Any, resp_url: str, **kwargs: Any):
        """
        初始化搜索响应解析器
        
        参数:
            resp_data: 原始响应数据
            resp_url: 响应URL
            **kwargs: 其他解析参数
        """
        self.origin: Any = resp_data
        self.url: str = resp_url
        self.raw: list[T] = []
        self._parse_response(resp_data, resp_url=resp_url, **kwargs)

    @abstractmethod
    def _parse_response(self, resp_data: Any, **kwargs: Any) -> None:
        """
        解析完整响应数据
        
        参数:
            resp_data: 原始响应数据
            **kwargs: 其他解析参数
            
        异常:
            NotImplementedError: 子类必须实现此方法
        """
        pass
        
    @abstractmethod
    def show_result(self) -> Optional[str]:
        """
        生成可读的搜索结果文本
        
        返回:
            Optional[str]: 格式化的搜索结果文本，无结果时返回None
            
        异常:
            NotImplementedError: 子类必须实现此方法
        """
        pass
