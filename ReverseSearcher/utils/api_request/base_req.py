"""搜索请求基类

所有搜索引擎请求类的抽象基类，继承 Network 提供统一的 HTTP 请求能力
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from ..network import RESP, Network
from ..response_parser.base_parser import BaseSearchResponse
from ..types import FileContent

T = TypeVar("T", bound=BaseSearchResponse[Any])


class BaseSearchReq(Network, ABC, Generic[T]):
    """搜索请求基类，继承 Network 的所有 HTTP 方法"""

    base_url: str = ""

    def __init__(
        self,
        base_url: str = "",
        network: Network | None = None,
        **request_kwargs: Any,
    ):
        if network is not None:
            # 使用外部传入的 Network 实例（复用其 client）
            self._client = network.client
            self._owned_client = False
        else:
            super().__init__(**request_kwargs)
            self._owned_client = True
        self.base_url = base_url

    @abstractmethod
    async def search(
        self,
        url: str | None = None,
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
            # 格式: (upload_url, form_data, file_field_name, json_path_list_or_None)
            (
                "https://tmpfiles.org/api/v1/upload",
                None,
                "file",
                ["data", "url"],
            ),
            (
                "https://uguu.se/upload.php",
                None,
                "files[]",
                ["files", 0, "url"],
            ),
            # 以下旧图床（纯文本响应）
            (
                "https://litterbox.catbox.moe/resources/internals/api.php",
                {"reqtype": "fileupload", "time": "1h"},
                "fileToUpload",
                None,
            ),
            (
                "https://tmp.ninja/upload.php",
                {"reqtype": "fileupload"},
                "fileToUpload",
                None,
            ),
        ]

        last_error = None
        for upload_url, data, field_name, json_path in hosts:
            try:
                resp = await self._client.post(
                    upload_url,
                    data=data,
                    files={field_name: ("image.jpg", file, "image/jpeg")},
                )
                resp.raise_for_status()
                text = resp.text.strip()

                # 尝试 JSON 解析
                if json_path:
                    import json

                    try:
                        obj = json.loads(text)
                        url = obj
                        for key in json_path:
                            url = url[key]
                        if isinstance(url, str) and url.startswith("http"):
                            url = (
                                url.replace("http://", "https://", 1)
                                if url.startswith("http://")
                                else url
                            )
                            # tmpfiles.org 返回的是 HTML 展示页，图片实际在 /dl/ 路径下
                            if "tmpfiles.org/" in url and "/dl/" not in url:
                                url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                            return url
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        pass

                # 纯文本 URL 响应
                if text.startswith("http"):
                    url = text
                    if "tmpfiles.org/" in url and "/dl/" not in url:
                        url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                    return url
            except Exception as e:
                last_error = e
                from astrbot.api import logger

                logger.debug(
                    f"[BaseSearchReq] Upload to {upload_url} failed, trying next: {e}"
                )
                continue

        raise RuntimeError(f"All image hosts failed, last error: {last_error}")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: Any | None = None,
    ) -> None:
        # 只有自己创建的 client 才关闭，复用的不关闭
        if getattr(self, "_owned_client", True):
            await self._client.aclose()

    async def _send_request(
        self,
        method: str,
        endpoint: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> RESP:
        """发送 HTTP 请求"""
        request_url = url or (
            f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        )
        method = method.lower()
        if method == "get":
            kwargs.pop("files", None)
            return await self.get(request_url, **kwargs)
        elif method == "post":
            return await self.post(request_url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
