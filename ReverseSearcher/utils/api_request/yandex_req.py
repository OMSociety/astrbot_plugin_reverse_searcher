from typing import Any, Optional, Union
from typing_extensions import override

from ..types import FileContent
from ..ext_tools import read_file
from ..response_parser.yandex_parser import YandexResponse
from .base_req import BaseSearchReq

class Yandex(BaseSearchReq[YandexResponse]):
    """
    Yandex 搜索请求类
    """
    def __init__(
        self,
        base_url: str = "https://yandex.com",
        **request_kwargs: Any,
    ):
        base_url = f"{base_url}/images/search"
        self.use_ru_fallback = request_kwargs.pop("use_ru_fallback", True)
        # max_results is passed to search() separately, but model.py also passes it to init.
        # We must pop it to avoid HandOver error.
        request_kwargs.pop("max_results", None)
        
        super().__init__(base_url, **request_kwargs)

    # ... (skipping search logic which is unchanged) ...

    @override
    async def _send_request(self, *args, **kwargs) -> Any:
        try:
            return await super()._send_request(*args, **kwargs)
        except Exception as e:
            # Simple fallback mechanism: replace .com with .ru in url
            if self.use_ru_fallback and "yandex.com" in self.base_url:
                # Update base_url for future calls logic (though search logic uses manual URLs mostly)
                # Currently 'search' override mostly constructs URLs manually unless we refactor it.
                # The 'search' method constructs: https://yandex.com/images/search...
                # If _send_request fails, it's because 'search' calls it.
                # However, 'search' constructs URL outside of _send_request if using 'url' param override.
                
                # Check if we are retrying a URL passed in args/kwargs
                # If we are here, super()._send_request failed.
                
                # We need to detect if we can swap .com to .ru in the params/url
                
                retry_needed = False
                
                # 1. Update self.base_url just in case
                if "yandex.com" in self.base_url:
                    self.base_url = self.base_url.replace("yandex.com", "yandex.ru")
                    retry_needed = True

                # 2. Update kwargs['url'] if present (this is what search uses)
                if "url" in kwargs and "yandex.com" in kwargs["url"]:
                    kwargs["url"] = kwargs["url"].replace("yandex.com", "yandex.ru")
                    retry_needed = True
                    
                if retry_needed:
                     return await super()._send_request(*args, **kwargs)
            
            raise e

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: FileContent = None,
        **kwargs: Any,
    ) -> YandexResponse:
        
        target_url = url
        if file:
            # Upload to Litterbox if file is provided
            # We need bytes. FileContent can be bytes, or generic file-like
            file_bytes = None
            if isinstance(file, bytes):
                file_bytes = file
            else:
                from ..ext_tools import read_file
                file_bytes = read_file(file)
            
            target_url = self._upload_to_litterbox(file_bytes)
        
        if not target_url:
             raise ValueError("Must provide url or file")

        # Yandex Search via URL
        # https://yandex.com/images/search?rpt=imageview&url={target_url}
        
        params = {
            "rpt": "imageview",
            "url": target_url
        }
        
        # Use headers to mimic browser
        headers = {
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # We use Requests directly or via _send_request (which uses self.session/requests)
        # BaseReq _send_request logic:
        # return await self.get(request_url, **kwargs)
        # We need to mix in our headers.
        
        # Since we are overriding params and headers, let's just call passing them.
        # Note: self.base_url is ".../images/search"
        
        # We might need to handle the specific Yandex URL structure.
        # _send_request uses self.base_url by default.
        
        # Let's try direct construction for clarity, or use the helper.
        # Helper: request_url = url or (f"{self.base_url}/{endpoint}" if endpoint else self.base_url)
        
        resp = await self._send_request(
            method="get",
            params=params,
            headers=headers,
            timeout=30
        )

        return YandexResponse(resp.text, resp.url, **kwargs)

    def _upload_to_litterbox(self, file: bytes) -> str:
        import requests
        # Simple upload implementation
        files = {'fileToUpload': ('image.jpg', file, 'image/jpeg')}
        data = {'reqtype': 'fileupload', 'time': '1h'}
        resp = requests.post("https://litterbox.catbox.moe/resources/internals/api.php", files=files, data=data, timeout=30)
        resp.raise_for_status()
        url = resp.text
        if not url.startswith("http"):
            raise Exception(f"Upload failed: {url}")
        return url

    @override
    async def _send_request(self, *args, **kwargs) -> Any:
        try:
            return await super()._send_request(*args, **kwargs)
        except Exception as e:
            # Simple fallback mechanism: replace .com with .ru in url
            if "yandex.com" in self.base_url:
                self.base_url = self.base_url.replace("yandex.com", "yandex.ru")
                # Retry
                # Note: 'url' in kwargs might also need replacing if it was absolute
                if "url" in kwargs and "yandex.com" in kwargs["url"]:
                    kwargs["url"] = kwargs["url"].replace("yandex.com", "yandex.ru")
                return await super()._send_request(*args, **kwargs)
            raise e
