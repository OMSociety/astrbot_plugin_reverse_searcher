from dataclasses import dataclass
from types import TracebackType
from typing import Any, Optional, Union
from httpx import AsyncClient, Proxy, QueryParams, create_ssl_context

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/99.0.4844.82 Safari/537.36"
    )
}


class Network:
    """
    网络请求客户端类
    
    封装httpx.AsyncClient，提供异步HTTP请求功能，
    支持代理、自定义头部、Cookie等设置
    """
    
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
        """
        初始化网络客户端
        
        参数:
            internal: 是否为内部客户端
            proxies: 代理服务器地址
            headers: 自定义HTTP头部
            cookies: Cookie字符串
            timeout: 请求超时时间(秒)
            verify_ssl: 是否验证SSL证书
            http2: 是否启用HTTP/2
        """
        self.internal: bool = internal
        headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.cookies: dict[str, str] = {}
        if cookies:
            self.cookies = {k.strip(): v for k, v in (c.strip().split("=", 1) 
                           for c in cookies.split(";") if "=" in c)}
        ssl_context = create_ssl_context(verify=verify_ssl)
        ssl_context.set_ciphers("DEFAULT")
        
        # 支持带认证的代理
        proxy_obj = None
        if proxies:
            # 检查是否包含认证信息 user:pass@host:port
            import re
            # 支持 user:pass@host 和 :pass@host 两种格式
            match = re.match(r'(https?|socks5)://(?:([^:@]+):)?([^:@]+)@(.+)', proxies)
            if match:
                scheme, user, password, url = match.groups()
                if user:
                    proxy_obj = Proxy(url=f"{scheme}://{url}", auth=(user, password))
                else:
                    proxy_obj = Proxy(url=f"{scheme}://{url}", auth=("", password))
            else:
                proxy_obj = proxies
        
        self.client: AsyncClient = AsyncClient(
            headers=headers,
            cookies=self.cookies,
            verify=ssl_context,
            http2=http2,
            proxy=proxy_obj,
            timeout=timeout,
            follow_redirects=True,
        )

    def start(self) -> AsyncClient:
        """
        获取客户端实例
        
        返回:
            AsyncClient: HTTP客户端实例
        """
        return self.client

    async def close(self) -> None:
        """
        关闭客户端连接
        """
        await self.client.aclose()

    async def __aenter__(self) -> AsyncClient:
        """
        异步上下文管理器入口
        
        返回:
            AsyncClient: HTTP客户端实例
        """
        return self.client

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_val: Optional[BaseException] = None,
        exc_tb: Optional[TracebackType] = None,
    ) -> None:
        """
        异步上下文管理器退出
        
        参数:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯
        """
        await self.client.aclose()


class ClientManager:
    """
    客户端管理器类
    
    管理HTTP客户端的生命周期，支持自定义客户端或创建新客户端
    """
    
    def __init__(
        self,
        client: Optional[AsyncClient] = None,
        proxies: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[str] = None,
        timeout: float = 30,
        verify_ssl: bool = True,
        http2: bool = False,
    ):
        """
        初始化客户端管理器
        
        参数:
            client: 现有的HTTP客户端实例
            proxies: 代理服务器地址
            headers: 自定义HTTP头部
            cookies: Cookie字符串
            timeout: 请求超时时间(秒)
            verify_ssl: 是否验证SSL证书
            http2: 是否启用HTTP/2
        """
        self.client: Union[Network, AsyncClient] = client or Network(
            internal=True,
            proxies=proxies,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            verify_ssl=verify_ssl,
            http2=http2,
        )

    async def __aenter__(self) -> AsyncClient:
        """
        异步上下文管理器入口
        
        返回:
            AsyncClient: HTTP客户端实例
        """
        return self.client.start() if isinstance(self.client, Network) else self.client

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_val: Optional[BaseException] = None,
        exc_tb: Optional[TracebackType] = None,
    ) -> None:
        """
        异步上下文管理器退出
        
        参数:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯
        """
        if isinstance(self.client, Network) and self.client.internal:
            await self.client.close()


@dataclass
class RESP:
    """
    HTTP响应数据类
    
    简化的HTTP响应表示，包含文本内容、URL和状态码
    """
    text: str
    url: str
    status_code: int
    headers: dict = None


class HandOver:
    """
    HTTP请求转发类
    
    提供简化的HTTP请求接口，支持GET、POST和下载操作
    """
    
    def __init__(
        self,
        client: Optional[AsyncClient] = None,
        proxies: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[str] = None,
        timeout: float = 30,
        verify_ssl: bool = True,
        http2: bool = False,
    ):
        """
        初始化HTTP请求转发器
        
        参数:
            client: 现有的HTTP客户端实例
            proxies: 代理服务器地址
            headers: 自定义HTTP头部
            cookies: Cookie字符串
            timeout: 请求超时时间(秒)
            verify_ssl: 是否验证SSL证书
            http2: 是否启用HTTP/2
        """
        self.client: Optional[AsyncClient] = client
        self.proxies: Optional[str] = proxies
        self.headers: Optional[dict[str, str]] = headers
        self.cookies: Optional[str] = cookies
        self.timeout: float = timeout
        self.verify_ssl: bool = verify_ssl
        self.http2: bool = http2
        # 创建一个单一的ClientManager实例
        self.client_manager = ClientManager(
            self.client,
            self.proxies,
            self.headers,
            self.cookies,
            self.timeout,
            self.verify_ssl,
            self.http2,
        )
        self._client_initialized = False
        self._managed_client = None

    async def _get_client(self) -> AsyncClient:
        """
        获取HTTP客户端实例
        
        返回:
            AsyncClient: HTTP客户端实例
        """
        if not self._client_initialized:
            self._managed_client = await self.client_manager.__aenter__()
            self._client_initialized = True
        return self._managed_client

    async def close(self) -> None:
        """
        关闭HTTP客户端连接
        """
        if self._client_initialized:
            await self.client_manager.__aexit__(None, None, None)
            self._client_initialized = False
            self._managed_client = None

    async def __aenter__(self) -> 'HandOver':
        """
        异步上下文管理器入口
        
        返回:
            HandOver: 当前实例
        """
        await self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_val: Optional[BaseException] = None,
        exc_tb: Optional[TracebackType] = None,
    ) -> None:
        """
        异步上下文管理器退出
        """
        await self.close()

    async def get(
        self,
        url: str,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> RESP:
        """
        执行GET请求
        
        参数:
            url: 请求URL
            params: URL查询参数
            headers: 自定义HTTP头部
            **kwargs: 其他请求参数
            
        返回:
            RESP: 简化的HTTP响应对象
        """
        client = await self._get_client()
        resp = await client.get(url, params=params, headers=headers, **kwargs)
        return RESP(resp.text, str(resp.url), resp.status_code, dict(resp.headers))

    async def post(
        self,
        url: str,
        params: Union[dict[str, Any], QueryParams, None] = None,
        headers: Optional[dict[str, str]] = None,
        data: Optional[dict[Any, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RESP:
        """
        执行POST请求
        
        参数:
            url: 请求URL
            params: URL查询参数
            headers: 自定义HTTP头部
            data: 表单数据
            files: 文件数据
            json: JSON数据
            **kwargs: 其他请求参数
            
        返回:
            RESP: 简化的HTTP响应对象
        """
        client = await self._get_client()
        resp = await client.post(
            url,
            params=params,
            headers=headers,
            data=data,
            files=files,
            json=json,
            **kwargs,
        )
        return RESP(resp.text, str(resp.url), resp.status_code, dict(resp.headers))

    async def download(self, url: str, headers: Optional[dict[str, str]] = None) -> bytes:
        """
        下载文件
        
        参数:
            url: 下载URL
            headers: 自定义HTTP头部
            
        返回:
            bytes: 下载的文件内容
        """
        client = await self._get_client()
        resp = await client.get(url, headers=headers)
        return resp.read()
