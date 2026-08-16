"""安全校验模块：SSRF 与本地文件读取防护

所有来自用户 / LLM 的图片引用（URL 或本地路径）在下载前必须经过本模块校验：

- URL：仅允许 http/https 且主机为**公网**地址。内网 / 环回 / 链路本地 /
  云元数据 / 保留 / 多播地址全部拒绝，并做 DNS 解析二次校验（防 DNS rebinding）。
- 本地路径：仅允许 AstrBot 数据目录内（QQ 官方等平台会把图片提前下载到
  `data/temp/`，file 字段为本地路径；任意其他本地路径一律拒绝）。

新增的图片引用入口（LLM 工具参数、消息内容解析）都必须调用 is_safe_image_ref。
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# 拒绝的本地主机名（不区分大小写）
_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "broadcasthost",
}

# 拒绝的主机名后缀（如 myhost.local、router.localhost）
_BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".home.arpa")

# 常见云元数据主机名（除 IP 段外的主机形式，如 GCP 的 metadata.google.internal）
_BLOCKED_METADATA_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.azure.internal",
    "instance-data",
    "instance-data.ec2.internal",
    "169.254.169.254.nip.io",
}


def is_private_ip(ip: str) -> bool:
    """判断 IP 是否属于内网 / 保留 / 元数据等不可信范围

    Args:
        ip: IP 字符串（IPv4 或 IPv6）

    Returns:
        True 表示内网或不可信地址，应拒绝访问。
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # 无法解析为合法 IP，保守拒绝
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def is_safe_image_url(url: str) -> bool:
    """校验图片 URL 是否安全（http/https + 公网主机）

    防 SSRF：拒绝内网 / 环回 / 链路本地 / 云元数据等地址；
    域名会做 DNS 解析二次校验，任一解析结果指向内网即拒绝（防 DNS rebinding）。

    Args:
        url: 待校验的 URL

    Returns:
        True 表示可安全请求。
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        logger.debug(f"[security] 拒绝非 http/https 协议: {url[:80]}")
        return False
    host = parsed.hostname
    if not host:
        return False
    host_lower = host.lower()

    if host_lower in _BLOCKED_HOSTNAMES or host_lower in _BLOCKED_METADATA_HOSTNAMES:
        return False
    if host_lower.endswith(_BLOCKED_HOST_SUFFIXES):
        return False

    # 主机为 IP 字面量：直接校验
    try:
        ip = ipaddress.ip_address(host)
        if is_private_ip(host):
            logger.debug(f"[security] 拒绝内网 IP: {url[:80]}")
            return False
        return True
    except ValueError:
        pass  # 是域名，继续 DNS 解析校验

    # DNS 解析二次校验：任一结果指向内网即拒绝
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        logger.debug(f"[security] 域名解析失败，保守拒绝: {host}")
        return False
    for info in infos:
        ip = info[4][0]
        if is_private_ip(ip):
            logger.debug(f"[security] 域名解析到内网，拒绝: {host} -> {ip}")
            return False
    return True


def is_safe_local_image_path(path: str) -> bool:
    """本地图片路径必须位于 AstrBot 数据目录内

    QQ 官方等平台会把图片提前下载到 `data/temp/`，file 字段是 data 目录下的
    本地路径；任意其他本地路径（如 /etc/passwd、D:\\secret.txt）一律拒绝，
    防止任意本地文件读取。

    Args:
        path: 本地文件路径

    Returns:
        True 表示路径在 AstrBot 数据目录内，可安全读取。
    """
    if not path or not isinstance(path, str):
        return False
    try:
        data_root = os.path.normpath(os.path.realpath(get_astrbot_data_path()))
        target = os.path.normpath(os.path.realpath(os.path.abspath(path)))
    except (OSError, ValueError):
        return False
    return target == data_root or target.startswith(data_root + os.sep)


def is_safe_image_ref(ref: str) -> bool:
    """统一校验图片引用（URL 或本地路径）

    Args:
        ref: 图片 URL 或本地路径

    Returns:
        True 表示引用安全，可用于下载。
    """
    if not ref or not isinstance(ref, str):
        return False
    ref = ref.strip()
    if ref.startswith(("http://", "https://")):
        return is_safe_image_url(ref)
    # file:// 协议直接拒绝（避免跨平台路径解析歧义，正常图片不会用该协议）
    if ref.lower().startswith("file://"):
        logger.debug(f"[security] 拒绝 file:// 协议: {ref[:80]}")
        return False
    return is_safe_local_image_path(ref)
