from typing import Any

from typing_extensions import override

from ..response_parser.yandex_parser import YandexResponse
from ..types import FileContent
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
            # .com 被 Yandex 风控时回退到 .ru 域名重试（search 内部 URL 基于 self.base_url 构造）
            if self.use_ru_fallback and "yandex.com" in self.base_url:
                self.base_url = self.base_url.replace("yandex.com", "yandex.ru")
                try:
                    return await super()._send_request(*args, **kwargs)
                except Exception:
                    pass
            raise e

    @override
    async def search(
        self,
        url: str | None = None,
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

            target_url = await self._upload_image(file_bytes)

        if not target_url:
            raise ValueError("Must provide url or file")

        # Yandex Search via URL
        # https://yandex.com/images/search?rpt=imageview&url={target_url}

        params = {"rpt": "imageview", "url": target_url}

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
            method="get", params=params, headers=headers, timeout=30
        )

        return YandexResponse(resp.text, resp.url, **kwargs)
