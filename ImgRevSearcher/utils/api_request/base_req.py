from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar
from ..response_parser.base_parser import BaseSearchResponse
from ..network import RESP, HandOver
from ..types import FileContent

ResponseT = TypeVar("ResponseT")
T = TypeVar("T", bound=BaseSearchResponse[Any])


class BaseSearchReq(HandOver, ABC, Generic[T]):
    """
    搜索请求基类
    
    所有搜索引擎请求类的抽象基类，提供通用的请求发送功能
    并定义搜索接口规范
    """
    base_url: str

    def __init__(self, base_url: str, **request_kwargs: Any):
        """
        初始化搜索请求基类
        
        参数:
            base_url: 搜索引擎API的基础URL
            **request_kwargs: 请求参数，传递给HandOver类
        """
        super().__init__(**request_kwargs)
        self.base_url = base_url

    @abstractmethod
    async def search(
        self,
        url: Optional[str] = None,
        file: FileContent = None,
        **kwargs: Any,
    ) -> T:
        """
        执行搜索请求
        
        参数:
            url: 图像URL
            file: 本地文件内容
            **kwargs: 其他搜索参数
            
        返回:
            T: 搜索响应对象
            
        异常:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    async def _upload_image(self, file: FileContent) -> str:
        """
        上传图片到Litterbox (临时图床)
        """
        # Ensure file content is valid
        if not file:
            raise ValueError("File content is empty or None")

        url = "https://litterbox.catbox.moe/resources/internals/api.php"
        data = {"reqtype": "fileupload", "time": "1h"}
        files = {"fileToUpload": ("image.jpg", file, "image/jpeg")}
        
        try:
             # Using self.client (httpx.AsyncClient)
             resp = await self.client.post(url, data=data, files=files)
             resp.raise_for_status()
             public_url = resp.text.strip()
             if not public_url.startswith("http"):
                  raise ValueError(f"Invalid upload response: {public_url}")
             return public_url
        except Exception as e:
             from astrbot.api import logger
             logger.error(f"[BaseSearchReq] Upload failed: {e}")
             raise e

    async def _send_request(self, method: str, endpoint: str = "", url: str = "", **kwargs: Any) -> RESP:
        """
        发送HTTP请求
        
        参数:
            method: HTTP方法(get/post)
            endpoint: API端点路径
            url: 完整的请求URL，如果提供则忽略base_url和endpoint
            **kwargs: 其他请求参数
            
        返回:
            RESP: HTTP响应对象
            
        异常:
            ValueError: 当提供了不支持的HTTP方法时抛出
        """
        request_url = url or (f"{self.base_url}/{endpoint}" if endpoint else self.base_url)
        method = method.lower()
        if method == "get":
            kwargs.pop("files", None)
            return await self.get(request_url, **kwargs)
        elif method == "post":
            return await self.post(request_url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
