from pathlib import Path
from typing import Any, Optional, Union
from typing_extensions import override
from ..response_parser import EHentaiResponse
from ..ext_tools import read_file
from .base_req import BaseSearchReq


class EHentai(BaseSearchReq[EHentaiResponse]):
    """
    E-Hentai搜索请求类
    
    用于与E-Hentai/ExHentai图像搜索功能交互，支持多种搜索选项
    """
    
    def __init__(
        self,
        is_ex: bool = False,
        covers: bool = False,
        similar: bool = True,
        exp: bool = False,
        **request_kwargs: Any,
    ):
        """
        初始化E-Hentai搜索请求
        
        参数:
            is_ex: 是否使用ExHentai而不是E-Hentai
            covers: 是否搜索封面图像
            similar: 是否搜索相似图像
            exp: 是否使用扩展搜索
            **request_kwargs: 其他请求参数
        """
        base_url = "https://upld.exhentai.org" if is_ex else "https://upld.e-hentai.org"
        super().__init__(base_url, **request_kwargs)
        self.is_ex: bool = is_ex
        self.covers: bool = covers
        self.similar: bool = similar
        self.exp: bool = exp

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: Union[str, bytes, Path, None] = None,
        **kwargs: Any,
    ) -> EHentaiResponse:
        """
        执行E-Hentai图像搜索
        
        参数:
            url: 图像URL
            file: 本地文件内容
            **kwargs: 其他搜索参数
            
        返回:
            EHentaiResponse: 搜索响应对象
            
        异常:
            ValueError: 当未提供url或file参数时抛出
        """
        endpoint = "upld/image_lookup.php" if self.is_ex else "image_lookup.php"
        data: dict[str, Any] = {"f_sfile": "File Search"}
        if url:
            # Add filename to tuple to enable Similarity Search
            files = {"sfile": ("image.jpg", await self.download(url), "application/octet-stream")}
        elif file:
            files = {"sfile": ("image.jpg", read_file(file), "application/octet-stream")}
        else:
            raise ValueError("Either 'url' or 'file' must be provided")
        if self.covers:
            data["fs_covers"] = "on"
        if self.similar:
            data["fs_similar"] = "on"
        if self.exp:
            data["fs_exp"] = "on"
        resp = await self._send_request(
            method="post",
            endpoint=endpoint,
            data=data,
            files=files,
        )
        return EHentaiResponse(resp.text, resp.url)
