"""GoogleLensResponse 响应解析测试（SerpApi 结构，离线纯解析）

覆盖 knowledge_graph 的结构异常形态（header_images 缺失 / [] / None、
knowledge_graph 本身为 null / []、header_images 首元素非 dict）：
任何一种都不得让解析抛异常，否则 ai_overview 与 visual_matches 会一起丢失。
"""

import json

from ReverseSearcher.utils.response_parser.google_lens_parser import GoogleLensResponse


def _payload(kg) -> str:
    return json.dumps(
        {
            "ai_overview": {"text": "AI 总览"},
            "visual_matches": [{"title": "视觉匹配", "link": "https://example.com/v"}],
            "knowledge_graph": kg,
        }
    )


def _kg_items(resp):
    return [item for item in resp.raw if item.source == "Knowledge Graph"]


def _visual_titles(resp):
    return [item.title for item in resp.raw if item.source != "Knowledge Graph"]


class TestKnowledgeGraphHeaderImages:
    """header_images 缺失 / [] / None 时解析不得中断"""

    def test_header_images_key_missing(self):
        resp = GoogleLensResponse(
            _payload({"description": "知识图谱描述"}), "http://serpapi"
        )
        assert resp.ai_overview == "AI 总览"
        assert len(_kg_items(resp)) == 1
        assert _kg_items(resp)[0].title == "Knowledge Graph"

    def test_header_images_empty_list(self):
        resp = GoogleLensResponse(
            _payload({"description": "知识图谱描述", "header_images": []}),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert len(_kg_items(resp)) == 1
        assert _kg_items(resp)[0].title == "Knowledge Graph"

    def test_header_images_none(self):
        resp = GoogleLensResponse(
            _payload({"description": "知识图谱描述", "header_images": None}),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert len(_kg_items(resp)) == 1
        assert _kg_items(resp)[0].title == "Knowledge Graph"

    def test_visual_matches_survive_missing_header_images(self):
        """整份响应继续解析：visual_matches 结果保留"""
        resp = GoogleLensResponse(
            _payload({"description": "知识图谱描述", "header_images": []}),
            "http://serpapi",
        )
        assert [item.title for item in resp.raw if item.source != "Knowledge Graph"] == [
            "视觉匹配"
        ]

    def test_header_images_still_used_when_present(self):
        """正常形态不回退：标题与缩略图取自 header_images[0]"""
        resp = GoogleLensResponse(
            _payload(
                {
                    "link": "https://example.com/kg",
                    "header_images": [
                        {"title": "图谱标题", "image": "https://example.com/k.png"}
                    ],
                }
            ),
            "http://serpapi",
        )
        items = _kg_items(resp)
        assert len(items) == 1
        assert items[0].title == "图谱标题"
        assert items[0].thumbnail == "https://example.com/k.png"
        assert items[0].url == "https://example.com/kg"


class TestKnowledgeGraphMalformed:
    """knowledge_graph 本身或其 header_images 元素结构异常时解析不得中断"""

    def test_knowledge_graph_null(self):
        resp = GoogleLensResponse(_payload(None), "http://serpapi")
        assert resp.ai_overview == "AI 总览"
        assert _visual_titles(resp) == ["视觉匹配"]
        assert _kg_items(resp) == []

    def test_knowledge_graph_list(self):
        resp = GoogleLensResponse(_payload([]), "http://serpapi")
        assert resp.ai_overview == "AI 总览"
        assert _visual_titles(resp) == ["视觉匹配"]
        assert _kg_items(resp) == []

    def test_header_images_first_element_null(self):
        resp = GoogleLensResponse(
            _payload({"description": "知识图谱描述", "header_images": [None]}),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert _visual_titles(resp) == ["视觉匹配"]
        items = _kg_items(resp)
        assert len(items) == 1
        assert items[0].title == "Knowledge Graph"

    def test_header_images_first_element_string(self):
        resp = GoogleLensResponse(
            _payload({"description": "知识图谱描述", "header_images": ["x"]}),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert _visual_titles(resp) == ["视觉匹配"]
        items = _kg_items(resp)
        assert len(items) == 1
        assert items[0].title == "Knowledge Graph"


class TestMalformedItemShapes:
    """单条/整批形态异常只跳过该条或该批，同批其它结果与 ai_overview 必须保留"""

    def test_visual_matches_null_item_skipped(self):
        resp = GoogleLensResponse(
            json.dumps(
                {
                    "ai_overview": {"text": "AI 总览"},
                    "visual_matches": [
                        None,
                        {"title": "正常条目", "link": "https://example.com/ok"},
                    ],
                }
            ),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert [item.title for item in resp.raw] == ["正常条目"]

    def test_visual_matches_string_item_skipped(self):
        resp = GoogleLensResponse(
            json.dumps(
                {
                    "ai_overview": {"text": "AI 总览"},
                    "visual_matches": [
                        "x",
                        {"title": "正常条目", "link": "https://example.com/ok"},
                    ],
                }
            ),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert [item.title for item in resp.raw] == ["正常条目"]

    def test_visual_matches_null_container(self):
        """visual_matches 本身为 null：整批无条目，但 ai_overview 保留"""
        resp = GoogleLensResponse(
            json.dumps({"ai_overview": {"text": "AI 总览"}, "visual_matches": None}),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert resp.raw == []

    def test_exact_matches_null_item_skipped(self):
        """exact_matches 与 visual_matches 同走 _add_serpapi_item，形态判断同样生效"""
        resp = GoogleLensResponse(
            json.dumps(
                {
                    "ai_overview": {"text": "AI 总览"},
                    "search_metadata": {"id": "s1"},
                    "exact_matches": [
                        None,
                        {"title": "精确条目", "link": "https://example.com/e"},
                    ],
                }
            ),
            "http://serpapi",
        )
        assert resp.ai_overview == "AI 总览"
        assert [item.title for item in resp.raw] == ["精确条目"]

    def test_zenserp_organic_null_item_skipped(self):
        """备引擎 Zenserp 的单条形态异常同样只跳过该条"""
        resp = GoogleLensResponse(
            json.dumps(
                {
                    "reverse_image_results": {
                        "organic": [
                            None,
                            {"title": "备引擎条目", "url": "https://example.com/z"},
                        ]
                    }
                }
            ),
            "https://app.zenserp.com/api/v2/search",
        )
        assert [item.title for item in resp.raw] == ["备引擎条目"]

    def test_zenserp_container_null(self):
        """reverse_image_results 为 null：备引擎解析就地放弃，不抛给调用方"""
        resp = GoogleLensResponse(
            json.dumps({"reverse_image_results": None}),
            "https://app.zenserp.com/api/v2/search",
        )
        assert resp.raw == []

    def test_zenserp_pages_null_item_skipped(self):
        """pages_with_matching_images 与 organic 共用同一生成器，独立断言一次"""
        resp = GoogleLensResponse(
            json.dumps(
                {
                    "reverse_image_results": {
                        "pages_with_matching_images": [
                            None,
                            {"title": "页面条目", "url": "https://example.com/p"},
                        ]
                    }
                }
            ),
            "https://app.zenserp.com/api/v2/search",
        )
        assert [item.title for item in resp.raw] == ["页面条目"]


class TestNonDictResponse:
    """整个响应 JSON 不是对象时在解析层就地降级，不抛给调用方"""

    def test_json_array_response(self):
        resp = GoogleLensResponse('["knowledge_graph"]', "http://serpapi")
        assert resp.raw == []
        assert resp.ai_overview == ""
        # 文案须点明未切换备引擎：本层就地降级，用户不会误以为“没配 Zenserp”
        assert resp.debug_info == "解析失败，响应类型: list（未切换备引擎）"

    def test_json_scalar_response(self):
        resp = GoogleLensResponse('"knowledge_graph"', "http://serpapi")
        assert resp.raw == []
        assert resp.ai_overview == ""
        assert resp.debug_info == "解析失败，响应类型: str（未切换备引擎）"
