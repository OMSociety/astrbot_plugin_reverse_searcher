"""网络请求客户端

封装 httpx.AsyncClient，提供异步 HTTP 请求功能，
支持代理、自定义头部、Cookie、超时、SSL 等设置。
直接支持 get/post/download 快捷方法，替代原来的 HandOver。
"""
from __future__ import annotations

import re
import ssl
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Optional, Union

import httpx
from httpx import AsyncClient, Proxy

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/99.0.4844.82 Safari/537.36"
    )
}


def _parse_proxy(proxies: Optional[str]) -> Optional[Union[str, Proxy]]:
    """解析代理字符串，支持带认证的格式"""
    if not proxies:
        return None
    # 支持格式: scheme://user:pass@host:port 或 scheme://:pass@host:port
    match = re.match(r"(https?|socks5)://(?:([^:@]+):)?([^:@]+)@(.+)", proxies)
    if match:
        scheme, user, password, url = match.groups()
        auth = (user, password) if user else ("", password)
        return Proxy(url=f"{scheme}://{url}", auth=auth)
    return proxies


@dataclass
class RESP:
    """简化 HTTP 响应"""
    text: str
    url: str
    status_code: int
    headers: dict


class Network:
    """异步 HTTP 客户端，支持上下文管理"""

    def __init__(
        self,
        internal: bool = False,
        proxies: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[str] = None,
        timeout: float = 30,
        verify_ssl: bool = True,
        http2: bool = False,
    ):
        self.internal = internal
        headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.cookies: dict[str, str] = {}
        if cookies:
            self.cookies = {
                k.strip(): v
                for k, v in (c.strip().split("=", 1) for c in cookies.split(";") if "=" in c)
            }

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = verify_ssl
        ssl_context.verify_mode = (
            ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE
        )
        ssl_context.set_ciphers("DEFAULT")

        proxy = _parse_proxy(proxies)

        self._client = AsyncClient(
            headers=headers,
            cookies=self.cookies,
            verify=ssl_context,
            http2=http2,
            proxy=proxy,
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def client(self) -> AsyncClient:
        """暴露底层 client 供外部直接使用（如上传文件）"""
        return self._client

    # ── 快捷方法 ──────────────────────────────────────────

    async def get(
        self,
        url: str,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> RESP:
        resp = await self._client.get(url, params=params, headers=headers, **kwargs)
        return RESP(resp.text, str(resp.url), resp.status_code, dict(resp.headers))

    async def post(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        data: Optional[dict[Any, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RESP:
        resp = await self._client.post(
            url, params=params, headers=headers, data=data, files=files, json=json, **kwargs
        )
        return RESP(resp.text, str(resp.url), resp.status_code, dict(resp.headers))

    async def download(self, url: str, headers: Optional[dict[str, str]] = None) -> bytes:
        resp = await self._client.get(url, headers=headers)
        return resp.read()

    # ── 生命周期 ──────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "Network":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_val: Optional[BaseException] = None,
        exc_tb: Optional[TracebackType] = None,
    ) -> None:
        if not self.internal:
            await self.close()
