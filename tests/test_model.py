"""BaseSearchModel 核心方法测试"""

import pytest
from ReverseSearcher.model import BaseSearchModel

# ── 测试用数据类 ────────────────────────────


class MockItem:
    """模拟解析条目：普通引擎结果（如 SauceNAO/Yandex/Google）"""

    def __init__(self, **attrs):
        self.title = attrs.get("title", "")
        self.url = attrs.get("url", "")
        self.similarity = attrs.get("similarity", 0)
        self.source = attrs.get("source", "")
        self.author = attrs.get("author", "")
        self.thumbnail = attrs.get("thumbnail", "")
        self.index_name = attrs.get("index_name", "")


class MockAnimeTraceItem:
    """模拟 AnimeTrace 条目：有 characters / box"""

    def __init__(self, characters=None):
        self.characters = characters or []
        self.box = (0, 0, 100, 100)


class MockCharacter:
    def __init__(self, name: str, work: str | None):
        self.name = name
        self.work = work


class TestBuildItemsFromRaw:
    """_build_items_from_raw 测试"""

    @pytest.fixture
    def model(self):
        return BaseSearchModel.__new__(BaseSearchModel)

    def test_empty_list(self, model):
        assert model._build_items_from_raw([]) == []

    def test_single_normal_item(self, model):
        item = MockItem(
            title="测试图片",
            url="https://example.com/1.jpg",
            similarity=85.5,
            source="pixiv",
            author="画师A",
            thumbnail="https://example.com/thumb.jpg",
        )
        result = model._build_items_from_raw([item])
        assert len(result) == 1
        assert result[0]["title"] == "测试图片"
        assert result[0]["url"] == "https://example.com/1.jpg"
        assert result[0]["similarity"] == "85.5%"
        assert result[0]["source"] == "pixiv"
        assert result[0]["author"] == "画师A"
        assert result[0]["thumbnail_url"] == "https://example.com/thumb.jpg"

    def test_fallback_source_to_index_name(self, model):
        item = MockItem(source="", index_name="Danbooru")
        result = model._build_items_from_raw([item])
        assert result[0]["source"] == "Danbooru"

    def test_truncates_to_five(self, model):
        items = [MockItem(title=f"item{i}") for i in range(10)]
        result = model._build_items_from_raw(items)
        assert len(result) == 5

    def test_missing_fields_default_empty(self, model):
        item = MockItem()
        result = model._build_items_from_raw([item])
        assert result[0]["title"] == ""
        assert result[0]["url"] == ""
        assert result[0]["source"] == ""
        assert result[0]["author"] == ""
        assert result[0]["thumbnail_url"] == ""

    def test_similarity_zero_returns_empty_string(self, model):
        item = MockItem(similarity=0)
        result = model._build_items_from_raw([item])
        assert result[0]["similarity"] == ""

    def test_similarity_string_passthrough(self, model):
        item = MockItem(similarity="high")
        result = model._build_items_from_raw([item])
        assert result[0]["similarity"] == "high"

    def test_animetrace_single_character(self, model):
        item = MockAnimeTraceItem(characters=[MockCharacter("初音未来", "VOCALOID")])
        result = model._build_items_from_raw([item])
        assert len(result) == 1
        assert result[0]["title"] == "角色: 初音未来"
        assert result[0]["source"] == "作品: VOCALOID"

    def test_animetrace_multi_character(self, model):
        item = MockAnimeTraceItem(
            characters=[MockCharacter(f"角色{i}", f"作品{i}") for i in range(3)]
        )
        result = model._build_items_from_raw([item])
        assert len(result) == 3
        assert result[0]["title"] == "角色: 角色0"
        assert result[2]["title"] == "角色: 角色2"

    def test_animetrace_capped_at_ten(self, model):
        item = MockAnimeTraceItem(
            characters=[MockCharacter(f"c{i}", f"w{i}") for i in range(15)]
        )
        result = model._build_items_from_raw([item])
        assert len(result) == 10

    def test_animetrace_no_work(self, model):
        item = MockAnimeTraceItem(characters=[MockCharacter("未知角色", None)])
        result = model._build_items_from_raw([item])
        assert result[0]["source"] == "AnimeTrace"


class TestPrepareEngineParams:
    """_prepare_engine_params 测试"""

    @pytest.fixture
    def model(self):
        return BaseSearchModel.__new__(BaseSearchModel)

    def test_ehentai_pop_params(self, model):
        params = {
            "url": "test",
            "is_ex": True,
            "covers": False,
            "similar": True,
            "exp": False,
            "cookies": {"sk": "val"},
            "keep_this": 42,
        }
        engine_params = model._prepare_engine_params("ehentai", params)
        assert engine_params["is_ex"] is True
        assert engine_params["covers"] is False
        assert engine_params["similar"] is True
        assert engine_params["exp"] is False
        assert engine_params["cookies"] == {"sk": "val"}
        assert "is_ex" not in params
        assert params["keep_this"] == 42

    def test_animetrace_pop_params(self, model):
        params = {"url": "test", "is_multi": True, "ai_detect": "l2"}
        engine_params = model._prepare_engine_params("animetrace", params)
        assert engine_params["is_multi"] is True
        assert engine_params["ai_detect"] == "l2"
        assert "is_multi" not in params
        assert "ai_detect" not in params

    def test_ascii2d_no_special_params(self, model):
        params = {"url": "test"}
        engine_params = model._prepare_engine_params("ascii2d", params)
        assert engine_params == {}

    def test_unknown_engine_no_pop(self, model):
        params = {"url": "test", "something": 99}
        engine_params = model._prepare_engine_params("unknown_engine", params)
        assert engine_params == {}
        assert params["something"] == 99


class TestFormatSimilarity:
    """_format_similarity 静态方法测试"""

    def test_float(self):
        assert BaseSearchModel._format_similarity(85.5) == "85.5%"

    def test_int(self):
        assert BaseSearchModel._format_similarity(100) == "100.0%"

    def test_zero(self):
        assert BaseSearchModel._format_similarity(0) == ""

    def test_negative(self):
        assert BaseSearchModel._format_similarity(-1) == "-1"

    def test_string(self):
        assert BaseSearchModel._format_similarity("high") == "high"

    def test_none(self):
        assert BaseSearchModel._format_similarity(None) == ""
