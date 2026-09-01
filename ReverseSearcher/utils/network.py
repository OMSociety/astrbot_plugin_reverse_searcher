"""网络请求客户端

封装 httpx.AsyncClient，提供异步 HTTP 请求功能，
支持代理、自定义头部、Cookie、超时、SSL 等设置。
直接支持 get/post/download 快捷方法，替代原来的 HandOver。
"""

from __future__ import annotations

import asyncio
import logging
import re
import ssl
from dataclasses import dataclass
from types import TracebackType
from typing import Any
from urllib.parse import urljoin

from httpx import AsyncClient, Proxy

from .security import is_safe_image_url

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/99.0.4844.82 Safari/537.36"
    )
}


def _parse_proxy(proxies: str | None) -> str | Proxy | None:
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

    # 手动跟随重定向的最大跳数（防 SSRF：公网 URL 302 到内网的防护上限）
    MAX_REDIRECTS = 3

    def __init__(
        self,
        internal: bool = False,
        proxies: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: str | None = None,
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
                for k, v in (
                    c.strip().split("=", 1) for c in cookies.split(";") if "=" in c
                )
            }

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = verify_ssl
        ssl_context.verify_mode = ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE
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
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> RESP:
        resp = await self._client.get(url, params=params, headers=headers, **kwargs)
        return RESP(resp.text, str(resp.url), resp.status_code, dict(resp.headers))

    async def post(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[Any, Any] | None = None,
        files: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> RESP:
        resp = await self._client.post(
            url,
            params=params,
            headers=headers,
            data=data,
            files=files,
            json=json,
            **kwargs,
        )
        return RESP(resp.text, str(resp.url), resp.status_code, dict(resp.headers))

    async def download(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """下载 URL 内容并返回 bytes。

        防 SSRF：这里不自动跟随重定向，改为手动逐跳跟随，并在每一跳
        用 is_safe_image_url 重新校验目标地址（公网 http/https），
        避免“初始 URL 已校验、但 302 到内网（169.254.169.254 等）”绕过。
        超过最大跳数或遇到不安全目标则停止并返回当前响应。

        Args:
            url: 待下载的 URL（应为公网图片地址）
            headers: 额外请求头

        Returns:
            响应 bytes；重定向链不安全/超限时返回最后一次（可能是 3xx）的 body。
        """
        current_url = url
        last_resp = None
        for _ in range(self.MAX_REDIRECTS):
            resp = await self._client.get(
                current_url, headers=headers, follow_redirects=False
            )
            last_resp = resp
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    break
                next_url = urljoin(str(current_url), location)
                if not await asyncio.to_thread(is_safe_image_url, next_url):
                    logger.warning(
                        f"[network] 拒绝不安全的重定向目标，停止跟随: "
                        f"{current_url} -> {next_url}"
                    )
                    break
                current_url = next_url
                continue
            return resp.read()
        return last_resp.read() if last_resp is not None else b""

    # ── 生命周期 ──────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Network:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        if not self.internal:
            await self.close()
