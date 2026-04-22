from json import loads as json_loads
from pathlib import Path
from typing import Any, Optional, Union
from typing_extensions import override
from ..response_parser import AnimeTraceResponse
from ..ext_tools import read_file
from .base_req import BaseSearchReq


class AnimeTrace(BaseSearchReq[AnimeTraceResponse]):
    """
    AnimeTrace搜索请求类
    
    用于识别动漫角色的图像搜索API接口
    """
    
    def __init__(
        self,
        base_url: str = "https://api.animetrace.com",
        endpoint: str = "v1/search",
        is_multi: Optional[int] = None,
        ai_detect: Optional[int] = None,
        **request_kwargs: Any,
    ):
        """
        初始化AnimeTrace搜索请求
        
        参数:
            base_url: API基础URL
            endpoint: API端点路径
            is_multi: 是否识别多个角色
            ai_detect: 是否进行AI生成图像检测
            **request_kwargs: 其他请求参数
        """
        base_url = f"{base_url}/{endpoint}"
        super().__init__(base_url, **request_kwargs)
        self.is_multi: Optional[int] = is_multi
        self.ai_detect: Optional[int] = ai_detect

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: Union[str, bytes, Path, None] = None,
        base64: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> AnimeTraceResponse:
        """
        执行AnimeTrace搜索
        
        参数:
            url: 图像URL
            file: 本地文件内容
            base64: Base64编码的图像数据
            model: 使用的识别模型
            **kwargs: 其他搜索参数
            
        返回:
            AnimeTraceResponse: 搜索响应对象
            
        异常:
            ValueError: 当未提供url、file或base64参数时抛出
        """
        params: dict[str, Any] = {}
        if self.is_multi:
            params["is_multi"] = self.is_multi
        if self.ai_detect:
            params["ai_detect"] = self.ai_detect
        if model:
            params["response_parser"] = model
        if url:
            data = {"url": url, **params}
            resp = await self._send_request(
                method="post",
                json=data,
            )
        elif file:
            files = {"file": read_file(file)}
            resp = await self._send_request(
                method="post",
                files=files,
                data=params or None,
            )
        elif base64:
            data = {"base64": base64, **params}
            resp = await self._send_request(
                method="post",
                json=data,
            )
        else:
            raise ValueError("One of 'url', 'file', or 'base64' must be provided")
        return AnimeTraceResponse(json_loads(resp.text), resp.url)
