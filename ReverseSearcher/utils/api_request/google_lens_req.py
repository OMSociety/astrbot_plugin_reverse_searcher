from typing import Any, Optional, Dict
from typing_extensions import override
import requests
import json

from ..response_parser.google_lens_parser import GoogleLensResponse
from .base_req import BaseSearchReq
from astrbot.api import logger

class GoogleLensSerpApi(BaseSearchReq[GoogleLensResponse]):
    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__("https://serpapi.com/search") # Pass base_url
        self.api_key = api_key
        # SerpApi params matched to user's example
        self.engine = "google_lens"

    @override
    async def search(self, file: Optional[bytes] = None, url: Optional[str] = None, **kwargs: Any) -> GoogleLensResponse:
        logger.info(f"[SerpApi] Searching via Google Lens engine...")
        
        params = {
            "engine": self.engine,
            "api_key": self.api_key,
            "country": kwargs.get("country", "us"), # Default US
            "hl": kwargs.get("hl", "en"),
            "q": kwargs.get("q"),
            "no_cache": kwargs.get("no_cache", False)
        }
        
        if url:
            params["url"] = url
        elif file:
            # SerpApi doesn't support direct binary upload via 'url' param easily unless we host it.
            # However, for simplicity and since we don't have a public URL for local files in this plugin structure efficiently (Litterbox is internal to Ascii2D utils),
            # Update: SerpApi documentation says they assume public URL.
            # But the user might provide a bytes object `file`. 
            # We must use proper handling.
            # Strategy: If file provided, upload to Litterbox first (reusing Ascii2D logic would be ideal but circular import risk).
            # ALTERNATIVE: SerpApi DOES NOT support direct image upload for Google Lens API easily without a URL.
            # Wait, Google Reverse Image API supports it, but Lens API usually needs a URL.
            # Let's revert to a quick Litterbox upload Helper or check if we can reuse the one from ascii2d (if refactored) or just duplicate the simple requests post.
            # Let's verify what the old code did. Old code used Selenium to upload.
            
            # For now, let's implement a quick temp host uploader here or use a common utility.
            # Better: Use the same Litterbox logic.
            url = self._upload_to_litterbox(file)
            params["url"] = url
        
        # Requests is blocking, wrap in thread if needed, but for now simple sync should be fine or use run_in_executor
        import asyncio
        data = await asyncio.to_thread(self._fetch_serpapi, params)
        
        # Parse logic
        # We need to convert SerpApi JSON to GoogleLensResponse
        # Use a special parser method or generic text
        # GoogleLensResponse expects (text, url, status_code, headers) usually, 
        # BUT since we have JSON, we might need to adapt the parser or return a mock RESP object with JSON string.
        
        return GoogleLensResponse(
            resp_data=json.dumps(data), 
            resp_url=f"https://serpapi.com/search?engine={self.engine}", 
            status_code=200, 
            headers={},
            **kwargs
        )

    def _fetch_serpapi(self, params):
        resp = requests.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        return resp.json()

    def _upload_to_litterbox(self, file: bytes) -> str:
        # Simple upload implementation
        files = {'fileToUpload': ('image.jpg', file, 'image/jpeg')}
        data = {'reqtype': 'fileupload', 'time': '1h'}
        resp = requests.post("https://litterbox.catbox.moe/resources/internals/api.php", files=files, data=data, timeout=30)
        resp.raise_for_status()
        url = resp.text
        if not url.startswith("http"):
            raise Exception(f"Upload failed: {url}")
        return url


class GoogleLensZenserp(BaseSearchReq[GoogleLensResponse]):
    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__("https://app.zenserp.com/api/v2/search")
        self.api_key = api_key

    @override
    async def search(self, file: Optional[bytes] = None, url: Optional[str] = None, **kwargs: Any) -> GoogleLensResponse:
        logger.info(f"[Zenserp] Searching via Google Reverse Image...")
        
        headers = {
            "apikey": self.api_key
        }
        params = {
            "gl": kwargs.get("country", "CN"),
            "hl": kwargs.get("hl", "zh-CN"),
        }
        
        if url:
            params["image_url"] = url
        elif file:
            url = self._upload_to_litterbox(file)
            params["image_url"] = url
            
        import asyncio
        data = await asyncio.to_thread(self._fetch_zenserp, headers, params)
        
        return GoogleLensResponse(
            resp_data=json.dumps(data), 
            resp_url="https://app.zenserp.com/api/v2/search", 
            status_code=200, 
            headers={},
            **kwargs
        )
        
    def _fetch_zenserp(self, headers, params):
        resp = requests.get("https://app.zenserp.com/api/v2/search", headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _upload_to_litterbox(self, file: bytes) -> str:
        files = {'fileToUpload': ('image.jpg', file, 'image/jpeg')}
        data = {'reqtype': 'fileupload', 'time': '1h'}
        resp = requests.post("https://litterbox.catbox.moe/resources/internals/api.php", files=files, data=data, timeout=30)
        resp.raise_for_status()
        url = resp.text
        if not url.startswith("http"):
             raise Exception(f"Upload failed: {url}")
        return url


class GoogleLens(BaseSearchReq[GoogleLensResponse]):
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
             logger.warning("[GoogleLens] No API keys configured. Functionality disabled.")

    @override
    async def search(self, file: Optional[bytes] = None, url: Optional[str] = None, **kwargs: Any) -> GoogleLensResponse:
        # Strategy: Primary -> Retry(Connection) -> Backup
        import asyncio
        
        # 1. Try Primary (if available)
        if self.primary:
             try:
                 return await self._try_search(self.primary, file, url, **kwargs)
             except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as e:
                 logger.warning(f"[GoogleLens] Primary Connection Error: {e}. Retrying once...")
                 try:
                     # Simple retry delay
                     await asyncio.sleep(1)
                     return await self._try_search(self.primary, file, url, **kwargs)
                 except Exception as retry_e:
                     logger.error(f"[GoogleLens] Primary Retry Failed: {retry_e}")
                     # Proceed to fallback
             except Exception as e:
                 logger.error(f"[GoogleLens] Primary Engine Failed: {e}")
                 # Proceed to fallback

        # 2. Try Backup (if available)
        if self.backup:
            logger.warning("[GoogleLens] Switching to Backup Engine (Zenserp)...")
            try:
                return await self._try_search(self.backup, file, url, **kwargs)
            except Exception as e:
                logger.error(f"[GoogleLens] Backup Engine Failed: {e}")
                # Both failed
        
        raise RuntimeError("Google Lens Search Failed: All configured engines exhausted.")

    async def _try_search(self, engine, file, url, **kwargs):
        return await engine.search(file=file, url=url, **kwargs)
