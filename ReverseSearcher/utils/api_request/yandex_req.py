from typing import Any

from typing_extensions import override

from ..ext_tools import read_file
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
        # max_results 在 search() 阶段使用，不会传给底层 httpx 客户端，这里先弹出避免报错
        request_kwargs.pop("max_results", None)

        super().__init__(base_url, **request_kwargs)

    @override
    async def _send_request(self, *args, **kwargs) -> Any:
        try:
            return await super()._send_request(*args, **kwargs)
        except Exception as e:
            # .com 被 Yandex 风控时回退到 .ru 域名重试
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
            # 本地文件先上传到临时图床（Litterbox），再以 URL 形式搜索
            file_bytes = file if isinstance(file, bytes) else read_file(file)
            target_url = await self._upload_image(file_bytes)

        if not target_url:
            raise ValueError("Must provide url or file")

        # Yandex 通过 URL 搜索：https://yandex.com/images/search?rpt=imageview&url={target_url}
        params = {"rpt": "imageview", "url": target_url}

        # 用浏览器 UA 头，降低被风控的概率
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        resp = await self._send_request(
            method="get", params=params, headers=headers, timeout=30
        )

        return YandexResponse(resp.text, resp.url, **kwargs)
