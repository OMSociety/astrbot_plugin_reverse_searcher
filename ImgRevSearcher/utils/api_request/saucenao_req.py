from json import loads as json_loads
from pathlib import Path
from typing import Any, Optional, Union
from httpx import QueryParams
from typing_extensions import override
from ..response_parser import SauceNAOResponse
from ..ext_tools import read_file
from .base_req import BaseSearchReq


class SauceNAO(BaseSearchReq[SauceNAOResponse]):
    """
    SauceNAO搜索请求类
    
    用于与SauceNAO图像搜索API交互，支持多种搜索参数配置
    """
    
    def __init__(
        self,
        base_url: str = "https://saucenao.com",
        api_key: Optional[str] = None,
        numres: int = 5,
        hide: int = 0,
        minsim: int = 30,
        output_type: int = 2,
        testmode: int = 0,
        dbmask: Optional[int] = None,
        dbmaski: Optional[int] = None,
        db: int = 999,
        dbs: Optional[list[int]] = None,
        **request_kwargs: Any,
    ):
        """
        初始化SauceNAO搜索请求
        
        参数:
            base_url: SauceNAO API的基础URL
            api_key: SauceNAO API密钥
            numres: 返回的结果数量
            hide: 隐藏选项(0=不隐藏，1=隐藏已知来源，2=隐藏未知来源，3=隐藏所有来源)
            minsim: 最小相似度阈值(0-100)
            output_type: 输出类型(0=HTML，1=XML，2=JSON)
            testmode: 测试模式(0=关闭，1=开启)
            dbmask: 数据库掩码
            dbmaski: 数据库索引掩码
            db: 数据库索引
            dbs: 数据库索引列表
            **request_kwargs: 其他请求参数
        """
        base_url = f"{base_url}/search.php"
        super().__init__(base_url, **request_kwargs)
        params: dict[str, Any] = {
            "testmode": testmode,
            "numres": numres,
            "output_type": output_type,
            "hide": hide,
            "db": db,
            "minsim": minsim,
        }
        if api_key is not None:
            params["api_key"] = api_key
        if dbmask is not None:
            params["dbmask"] = dbmask
        if dbmaski is not None:
            params["dbmaski"] = dbmaski
        self.params: QueryParams = QueryParams(params)
        if dbs is not None:
            self.params = self.params.remove("db")
            for i in dbs:
                self.params = self.params.add("dbs[]", i)

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: Union[str, bytes, Path, None] = None,
        **kwargs: Any,
    ) -> SauceNAOResponse:
        """
        执行SauceNAO图像搜索
        
        参数:
            url: 图像URL
            file: 本地文件内容
            **kwargs: 其他搜索参数
            
        返回:
            SauceNAOResponse: 搜索响应对象
            
        异常:
            ValueError: 当未提供url或file参数时抛出
        """
        params = self.params
        files: Optional[dict[str, Any]] = None
        if url:
            params = params.add("url", url)
        elif file:
            files = {"file": read_file(file)}
        else:
            raise ValueError("Either 'url' or 'file' must be provided")
        resp = await self._send_request(
            method="post",
            params=params,
            files=files,
        )
        resp_json = json_loads(resp.text)
        resp_json.update({"status_code": resp.status_code})
        return SauceNAOResponse(resp_json, resp.url)
