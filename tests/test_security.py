"""
安全校验模块测试（SSRF / 本地文件读取防护）

测试 security.py 的 IP 判定、URL 公网校验（含 DNS rebinding 防护）、
本地路径目录白名单、统一入口 is_safe_image_ref。
域名解析用例通过 monkeypatch 避免真实 DNS。
"""

import os
import socket

import pytest
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from ReverseSearcher.utils.security import (
    is_private_ip,
    is_safe_image_ref,
    is_safe_image_url,
    is_safe_local_image_path,
)


@pytest.fixture(autouse=True)
def _clear_dns_cache():
    """每个用例前清空进程级 DNS 缓存，避免 mock 与真实解析结果跨用例污染"""
    from ReverseSearcher.utils import security

    security._DNS_CACHE.clear()


def _mock_dns_public(monkeypatch):
    """把 DNS 解析 mock 为公网 IP，使「公网 URL 应放行」用例不依赖真实网络环境。

    沙箱/挂代理的机器（Clash fake-ip 等）系统 DNS 会返回私有段合成地址，
    真实解析会让这些用例假失败；防护逻辑本身由 rebinding 专项用例覆盖。
    """
    monkeypatch.setattr(
        "ReverseSearcher.utils.security.socket.getaddrinfo",
        lambda host, port: [(socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))],
    )


class TestIsPrivateIp:
    """内网/保留地址判定"""

    @staticmethod
    def _cases():
        return {
            "127.0.0.1": True,  # 环回
            "10.0.0.1": True,  # 私网 A 类
            "192.168.1.1": True,  # 私网 C 类
            "172.16.0.1": True,  # 私网 B 类
            "169.254.169.254": True,  # 链路本地/云元数据
            "0.0.0.0": True,  # 未指定
            "::1": True,  # IPv6 环回
            "fc00::1": True,  # IPv6 唯一本地
            "fe80::1": True,  # IPv6 链路本地
            "8.8.8.8": False,  # 公网
            "1.1.1.1": False,
            "114.114.114.114": False,
            "not-an-ip": True,  # 非法 → 保守拒绝
        }

    def test_all(self):
        for ip, expected in self._cases().items():
            assert is_private_ip(ip) is expected, f"is_private_ip({ip})"

    def test_ipv6_global_public(self):
        assert is_private_ip("2606:4700:4700::1111") is False  # Cloudflare IPv6


class TestIsSafeImageUrl:
    """URL 公网校验（SSRF 防护）"""

    def test_public_https_url(self, monkeypatch):
        _mock_dns_public(monkeypatch)
        assert is_safe_image_url("https://example.com/a.jpg") is True

    def test_public_http_url(self, monkeypatch):
        _mock_dns_public(monkeypatch)
        assert is_safe_image_url("http://example.com/a.png") is True

    def test_private_ip_url(self):
        assert is_safe_image_url("https://127.0.0.1:8443/x.jpg") is False
        assert is_safe_image_url("http://192.168.1.1/x.png") is False
        assert is_safe_image_url("http://169.254.169.254/latest/meta-data/") is False
        assert is_safe_image_url("https://10.0.0.5/x.gif") is False

    def test_bad_protocol(self):
        assert is_safe_image_url("ftp://example.com/x.jpg") is False
        assert is_safe_image_url("file:///etc/passwd") is False
        assert is_safe_image_url("javascript:alert(1)") is False

    def test_localhost_hostname(self):
        assert is_safe_image_url("https://localhost/x.jpg") is False

    def test_local_suffix_hostname(self):
        assert is_safe_image_url("https://router.local/x.jpg") is False
        assert is_safe_image_url("https://myhost.internal/x.jpg") is False

    def test_metadata_hostname(self):
        assert is_safe_image_url("http://metadata.google.internal/x.jpg") is False

    def test_empty_and_invalid(self):
        assert is_safe_image_url("") is False
        assert is_safe_image_url(None) is False
        assert is_safe_image_url("   ") is False
        assert is_safe_image_url("not a url") is False

    def test_domain_resolves_to_private(self, monkeypatch):
        """DNS rebinding 防护：域名解析到内网 → 拒绝"""
        monkeypatch.setattr(
            "ReverseSearcher.utils.security.socket.getaddrinfo",
            lambda host, port: [
                (socket.AF_INET, 0, 0, "", ("127.0.0.1", 0)),
                (socket.AF_INET, 0, 0, "", ("10.0.0.2", 0)),
            ],
        )
        assert is_safe_image_url("https://evil.example.com/x.jpg") is False

    def test_domain_resolves_to_public(self, monkeypatch):
        """域名解析到公网 → 放行"""
        monkeypatch.setattr(
            "ReverseSearcher.utils.security.socket.getaddrinfo",
            lambda host, port: [(socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))],
        )
        assert is_safe_image_url("https://safe.example.com/x.jpg") is True

    def test_domain_resolve_failure(self, monkeypatch):
        """DNS 解析失败 → 保守拒绝"""
        monkeypatch.setattr(
            "ReverseSearcher.utils.security.socket.getaddrinfo",
            lambda host, port: (_ for _ in ()).throw(socket.gaierror("nxdomain")),
        )
        assert is_safe_image_url("https://nxdomain.invalid/x.jpg") is False


class TestIsSafeLocalImagePath:
    """本地路径目录白名单"""

    def _data_path(self, *parts) -> str:
        return os.path.join(get_astrbot_data_path(), *parts)

    def test_inside_data_dir(self):
        # QQ 官方等平台预下载图片位于 data/temp/
        assert is_safe_local_image_path(self._data_path("temp", "image_1.jpg")) is True
        assert is_safe_local_image_path(get_astrbot_data_path()) is True

    def test_outside_data_dir(self):
        assert is_safe_local_image_path("/etc/passwd") is False
        assert is_safe_local_image_path(r"C:\Windows\system32\config\SAM") is False
        assert is_safe_local_image_path("relative/path.jpg") is False

    def test_empty(self):
        assert is_safe_local_image_path("") is False
        assert is_safe_local_image_path(None) is False


class TestIsSafeImageRef:
    """统一图片引用入口"""

    def test_public_url_ok(self, monkeypatch):
        _mock_dns_public(monkeypatch)
        assert is_safe_image_ref("https://example.com/a.jpg") is True

    def test_private_url_rejected(self):
        assert is_safe_image_ref("https://127.0.0.1/x.jpg") is False

    def test_file_protocol_rejected(self):
        assert is_safe_image_ref("file:///etc/passwd") is False

    def test_local_path_inside_data(self):
        p = os.path.join(get_astrbot_data_path(), "temp", "x.png")
        assert is_safe_image_ref(p) is True

    def test_local_path_outside_data(self):
        assert is_safe_image_ref("/etc/shadow") is False

    def test_empty(self):
        assert is_safe_image_ref("") is False
        assert is_safe_image_ref(None) is False
