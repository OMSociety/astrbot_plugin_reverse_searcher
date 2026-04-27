import json
from typing import Any

import httpx
from typing_extensions import override

from astrbot.api import logger

from ..response_parser.google_lens_parser import GoogleLensResponse
from .base_req import BaseSearchReq


class GoogleLensSerpApi(BaseSearchReq[GoogleLensResponse]):
    """SerpApi 实现：通过 Google Lens 引擎搜索图片。

    SerpApi 只接受公开 URL，本地文件需要先上传到图床再传入。
    """

    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__("https://serpapi.com/search")
        self.api_key = api_key
        self.engine = "google_lens"

    @override
    async def search(
        self, file: bytes | None = None, url: str | None = None, **kwargs: Any
    ) -> GoogleLensResponse:
        """执行 SerpApi Google Lens 搜索。

        参数:
            file: 本地图片 bytes（会上传到图床后转 URL）
            url: 公开图片 URL（优先级高于 file）
            kwargs: 可包含 country, hl, q, no_cache

        返回:
            GoogleLensResponse 包含序列化后的搜索结果 JSON
        """
        logger.info("[SerpApi] Searching via Google Lens engine...")

        params = {
            "engine": self.engine,
            "api_key": self.api_key,
            "country": kwargs.get("country", "us"),
            "hl": kwargs.get("hl", "en"),
            "q": kwargs.get("q"),
            "no_cache": kwargs.get("no_cache", False),
        }

        if url:
            params["url"] = url
        elif file:
            # SerpApi 只接受公开 URL，本地文件先上传到临时图床
            url = await self._upload_image(file)
            params["url"] = url

        data = await self._fetch_serpapi(params)

        return GoogleLensResponse(
            resp_data=json.dumps(data),
            resp_url=f"https://serpapi.com/search?engine={self.engine}",
            **kwargs,
        )

    async def _fetch_serpapi(self, params: dict) -> dict:
        """调用 SerpApi 搜索接口并返回 JSON 结果"""
        resp = await self._client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        return resp.json()


class GoogleLensZenserp(BaseSearchReq[GoogleLensResponse]):
    """Zenserp 实现：通过 Google Reverse Image 引擎搜索图片。

    同样只接受公开 URL，本地文件需先上传到图床。
    """

    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__("https://app.zenserp.com/api/v2/search")
        self.api_key = api_key

    @override
    async def search(
        self, file: bytes | None = None, url: str | None = None, **kwargs: Any
    ) -> GoogleLensResponse:
        """执行 Zenserp Google Reverse Image 搜索。

        参数:
            file: 本地图片 bytes（会上传到图床后转 URL）
            url: 公开图片 URL（优先级高于 file）
            kwargs: 可包含 country, hl

        返回:
            GoogleLensResponse
        """
        logger.info("[Zenserp] Searching via Google Reverse Image...")

        headers = {"apikey": self.api_key}
        params = {
            "gl": kwargs.get("country", "CN"),
            "hl": kwargs.get("hl", "zh-CN"),
        }

        if url:
            params["image_url"] = url
        elif file:
            url = await self._upload_image(file)
            params["image_url"] = url

        data = await self._fetch_zenserp(headers, params)

        return GoogleLensResponse(
            resp_data=json.dumps(data),
            resp_url="https://app.zenserp.com/api/v2/search",
            **kwargs,
        )

    async def _fetch_zenserp(self, headers: dict, params: dict) -> dict:
        """调用 Zenserp 搜索接口并返回 JSON 结果"""
        resp = await self._client.get(
            "https://app.zenserp.com/api/v2/search", headers=headers, params=params
        )
        resp.raise_for_status()
        return resp.json()


class GoogleLens(BaseSearchReq[GoogleLensResponse]):
    """Google Lens 搜索编排器。

    按优先级选择子引擎：
        1. SerpApi (google_lens) — 主引擎
        2. Zenserp (google_reverse_image) — 备引擎

    主引擎失败时会自动切换到备引擎。
    """

    def __init__(self, **kwargs: Any):
        super().__init__("https://google.com")
        self.api_keys = kwargs.get("api_keys", {})
        self.serpapi_key = self.api_keys.get("serpapi") or kwargs.get("serpapi_key")
        self.zenserp_key = self.api_keys.get("zenserp") or kwargs.get("zenserp_key")

        self.primary = None
        self.backup = None

        if self.serpapi_key:
            self.primary = GoogleLensSerpApi(self.serpapi_key, **kwargs)
            logger.info("[GoogleLens] Primary Engine: SerpApi (Google Lens)")

        if self.zenserp_key:
            self.backup = GoogleLensZenserp(self.zenserp_key, **kwargs)
            logger.info("[GoogleLens] Backup Engine: Zenserp (Google Reverse Image)")

        if not self.primary and not self.backup:
            logger.warning(
                "[GoogleLens] No API keys configured. Functionality disabled."
            )

    @override
    async def search(
        self, file: bytes | None = None, url: str | None = None, **kwargs: Any
    ) -> GoogleLensResponse:
        """执行搜索，主引擎优先，失败后自动降级到备引擎。

        策略:
            1. 尝试主引擎 (SerpApi)
            2. 连接错误时重试一次
            3. 仍失败则切换到备引擎 (Zenserp)
            4. 全部失败则抛 RuntimeError
        """
        import asyncio

        # 1. Try Primary (if available)
        if self.primary:
            try:
                return await self._try_search(self.primary, file, url, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as e:
                logger.warning(
                    f"[GoogleLens] Primary Connection Error: {e}. Retrying once..."
                )
                try:
                    await asyncio.sleep(1)
                    return await self._try_search(self.primary, file, url, **kwargs)
                except Exception as retry_e:
                    logger.error(f"[GoogleLens] Primary Retry Failed: {retry_e}")
            except Exception as e:
                logger.error(f"[GoogleLens] Primary Engine Failed: {e}")

        # 2. Try Backup (if available)
        if self.backup:
            logger.warning("[GoogleLens] Switching to Backup Engine (Zenserp)...")
            try:
                return await self._try_search(self.backup, file, url, **kwargs)
            except Exception as e:
                logger.error(f"[GoogleLens] Backup Engine Failed: {e}")

        raise RuntimeError(
            "Google Lens Search Failed: All configured engines exhausted."
        )

    async def _try_search(self, engine, file, url, **kwargs):
        """委托给子引擎执行搜索"""
        return await engine.search(file=file, url=url, **kwargs)
