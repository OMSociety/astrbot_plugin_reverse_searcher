"""搜索请求基类

所有搜索引擎请求类的抽象基类，继承 Network 提供统一的 HTTP 请求能力
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

from ..response_parser.base_parser import BaseSearchResponse
from ..network import Network, RESP
from ..types import FileContent

T = TypeVar("T", bound=BaseSearchResponse[Any])


class BaseSearchReq(Network, ABC, Generic[T]):
    """搜索请求基类，继承 Network 的所有 HTTP 方法"""

    base_url: str = ""

    def __init__(self, base_url: str = "", **request_kwargs: Any):
        super().__init__(**request_kwargs)
        self.base_url = base_url

    @abstractmethod
    async def search(
        self,
        url: Optional[str] = None,
        file: FileContent = None,
        **kwargs: Any,
    ) -> T:
        """执行搜索，子类必须实现"""
        raise NotImplementedError

    async def _upload_image(self, file: FileContent) -> str:
        """上传图片到临时图床（catbox → fallback chain）"""
        if not file:
            raise ValueError("File content is empty or None")

        hosts = [
            ("https://litterbox.catbox.moe/resources/internals/api.php", {"reqtype": "fileupload", "time": "1h"}),
            ("https://tmp.ninja/upload.php", {"reqtype": "fileupload"}),
        ]

        last_error = None
        for upload_url, data in hosts:
            try:
                resp = await self._client.post(
                    upload_url,
                    data=data,
                    files={"fileToUpload": ("image.jpg", file, "image/jpeg")},
                )
                resp.raise_for_status()
                public_url = resp.text.strip()
                if public_url.startswith("http"):
                    return public_url
            except Exception as e:
                last_error = e
                from astrbot.api import logger
                logger.debug(f"[BaseSearchReq] Upload to {upload_url} failed, trying next: {e}")
                continue

        raise RuntimeError(f"All image hosts failed, last error: {last_error}")

    async def _send_request(
        self,
        method: str,
        endpoint: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> RESP:
        """发送 HTTP 请求"""
        request_url = url or (f"{self.base_url}/{endpoint}" if endpoint else self.base_url)
        method = method.lower()
        if method == "get":
            kwargs.pop("files", None)
            return await self.get(request_url, **kwargs)
        elif method == "post":
            return await self.post(request_url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")