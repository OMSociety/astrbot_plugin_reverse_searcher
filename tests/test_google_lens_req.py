"""GoogleLens 搜索编排器核心测试

GoogleLens 是 SerpApi → Zenserp 的 fallback 编排器。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from ReverseSearcher.utils.api_request.google_lens_req import (
    GoogleLens,
    GoogleLensSerpApi,
    GoogleLensZenserp,
)


class TestGoogleLensInit:
    """构造函数与引擎选择逻辑测试"""

    def test_no_keys_configured(self):
        """无 API key → primary 和 backup 均为 None"""
        gl = GoogleLens(api_keys={})
        assert gl.primary is None
        assert gl.backup is None

    def test_serpapi_only(self):
        """仅配置 serpapi → primary 为 SerpApi"""
        gl = GoogleLens(api_keys={"serpapi": "sk-test"})
        assert isinstance(gl.primary, GoogleLensSerpApi)
        assert gl.primary.api_key == "sk-test"
        assert gl.backup is None

    def test_zenserp_only(self):
        """仅配置 zenserp → backup 为 Zenserp"""
        gl = GoogleLens(api_keys={"zenserp": "zk-test"})
        assert gl.primary is None
        assert isinstance(gl.backup, GoogleLensZenserp)
        assert gl.backup.api_key == "zk-test"

    def test_both_keys(self):
        """两个 key 都有 → 两级引擎都配置"""
        gl = GoogleLens(api_keys={"serpapi": "sk-a", "zenserp": "zk-b"})
        assert isinstance(gl.primary, GoogleLensSerpApi)
        assert isinstance(gl.backup, GoogleLensZenserp)
        assert gl.primary.api_key == "sk-a"
        assert gl.backup.api_key == "zk-b"

    def test_legacy_flat_keys(self):
        """兼容旧的顶层字段传 key"""
        gl = GoogleLens(serpapi_key="sk-legacy", zenserp_key="zk-legacy")
        assert isinstance(gl.primary, GoogleLensSerpApi)
        assert isinstance(gl.backup, GoogleLensZenserp)


class TestGoogleLensSearch:
    """search 方法 fallback 策略测试"""

    @pytest.fixture
    def mock_primary_success(self):
        """主引擎直接成功"""
        primary = MagicMock()
        primary.search = AsyncMock(
            return_value=MagicMock(
                resp_data='{"results":[]}', resp_url="http://serpapi"
            )
        )
        return primary

    @pytest.fixture
    def mock_primary_fail_backup_success(self):
        """主引擎失败，备引擎成功"""
        primary = MagicMock()
        primary.search = AsyncMock(side_effect=Exception("SerpApi down"))
        backup = MagicMock()
        backup.search = AsyncMock(
            return_value=MagicMock(
                resp_data='{"results":[]}', resp_url="http://zenserp"
            )
        )
        return primary, backup

    def test_primary_success(self, mock_primary_success):
        """主引擎成功 → 返回结果"""
        gl = GoogleLens(api_keys={})
        gl.primary = mock_primary_success
        gl.backup = None

        # 用 asyncio 同步执行
        import asyncio

        result = asyncio.run(gl.search(url="https://example.com/img.jpg"))
        assert result is not None
        mock_primary_success.search.assert_called_once()

    def test_primary_fail_backup_success(self, mock_primary_fail_backup_success):
        """主引擎失败 → 自动降级到备引擎"""
        primary, backup = mock_primary_fail_backup_success
        gl = GoogleLens(api_keys={})
        gl.primary = primary
        gl.backup = backup

        import asyncio

        result = asyncio.run(gl.search(url="https://example.com/img.jpg"))
        assert result is not None
        primary.search.assert_called_once()
        backup.search.assert_called_once()

    def test_all_fail_raises(self):
        """全部引擎失败 → RuntimeError"""
        primary = MagicMock()
        primary.search = AsyncMock(side_effect=Exception("fail1"))
        backup = MagicMock()
        backup.search = AsyncMock(side_effect=Exception("fail2"))

        gl = GoogleLens(api_keys={})
        gl.primary = primary
        gl.backup = backup

        import asyncio

        with pytest.raises(RuntimeError, match="All configured engines exhausted"):
            asyncio.run(gl.search(url="https://example.com/img.jpg"))

    def test_no_engines_raises(self):
        """完全没有引擎 → RuntimeError"""
        gl = GoogleLens(api_keys={})
        gl.primary = None
        gl.backup = None

        import asyncio

        with pytest.raises(RuntimeError, match="All configured engines exhausted"):
            asyncio.run(gl.search(url="https://example.com/img.jpg"))


class TestGoogleLensPrivateMethods:
    """_try_search 委托方法测试"""

    def test_try_search_returns_engine_result(self):
        """_try_search 正确委托给子引擎"""
        engine = MagicMock()
        expected = MagicMock()
        engine.search = AsyncMock(return_value=expected)

        gl = GoogleLens(api_keys={})
        import asyncio

        result = asyncio.run(gl._try_search(engine, None, "http://x.com/a.jpg"))
        assert result is expected
        engine.search.assert_called_once_with(file=None, url="http://x.com/a.jpg")
