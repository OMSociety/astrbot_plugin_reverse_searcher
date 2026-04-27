"""引擎注册中心 — 单一数据源

所有引擎元数据、请求类映射、意图路由集中于此。
main.py / search_tools.py / model.py 从本文件引。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

# 前向声明类型占位，实际引用由调用方注入
TYPE_REQUEST_CLASS = type


# ── 引擎定义 ──────────────────────────────────────────


@dataclass
class EngineDef:
    """单个搜索引擎的完整元数据"""

    name: str  # 内部标识
    label: str  # 展示名
    desc: str  # 功能描述
    url: str  # 官网/入口
    anime_focused: bool  # 是否二次元专用
    color: tuple[int, int, int]  # 主题色 (用于卡片/表格)

    # 运行时引用
    req_class: TYPE_REQUEST_CLASS | None = None  # api_request 请求类

    # LLM 工具用
    fallback: list[str] = field(default_factory=list)  # 自动切换候补


# ── 注册表 ────────────────────────────────────────────

ENGINE_REGISTRY: dict[str, EngineDef] = {
    "animetrace": EngineDef(
        name="animetrace",
        label="AnimeTrace",
        desc="动漫角色识别（最强）",
        url="https://www.animetrace.com/",
        anime_focused=True,
        color=(99, 102, 241),  # #6366F1 靛蓝紫
        fallback=["saucenao"],
    ),
    "saucenao": EngineDef(
        name="saucenao",
        label="SauceNAO",
        desc="综合出处搜索",
        url="https://saucenao.com/",
        anime_focused=True,
        color=(30, 30, 46),  # #1E1E2E 暗炭黑
        fallback=["google"],
    ),
    "ehentai": EngineDef(
        name="ehentai",
        label="E-Hentai",
        desc="同人本/汉化组搜索",
        url="https://e-hentai.org/",
        anime_focused=True,
        color=(220, 55, 75),  # #DC374B 绯红
    ),
    "google": EngineDef(
        name="google",
        label="Google 图片",
        desc="综合搜索引擎",
        url="https://lens.google.com/",
        anime_focused=False,
        color=(66, 133, 244),
        fallback=["yandex"],
    ),
    "yandex": EngineDef(
        name="yandex",
        label="Yandex",
        desc="相似图片搜索",
        url="https://yandex.com/images/",
        anime_focused=False,
        color=(255, 204, 0),
        fallback=["google"],
    ),
}

# 便捷别名
ALL_ENGINES: list[str] = list(ENGINE_REGISTRY.keys())

# 兼容旧 COLOR_THEME（绘制表格用）
COLOR_THEME: dict[str, tuple] = {
    "bg": (255, 255, 255),
    "header_bg": (67, 99, 216),
    "header_text": (255, 255, 255),
    "table_header": (240, 242, 245),
    "cell_bg_even": (250, 250, 252),
    "cell_bg_odd": (255, 255, 255),
    "border": (180, 185, 195),
    "text": (50, 50, 50),
    "url": (41, 98, 255),
    "success": (76, 175, 80),
    "fail": (244, 67, 54),
    "shadow": (0, 0, 0, 30),
    "hint": (100, 100, 100),
}


# ── 意图路由器 ──────────────────────────────────────────

INTENT_KEYWORD_WEIGHTS: dict[str, dict[str, int]] = {
    "animetrace": {
        "角色": 10,
        "角色名": 10,
        "是谁": 8,
        "哪个人物": 8,
        "动漫角色": 10,
        "cos": 8,
        "动画": 5,
        "番剧": 5,
        "画风": 3,
        "画师风格": 3,
    },
    "saucenao": {
        "出处": 10,
        "来源": 10,
        "画师": 10,
        "作者": 8,
        "pixiv": 6,
        "pid": 6,
        "作品": 5,
        "原图": 4,
    },
    "ehentai": {
        "同人": 10,
        "本子": 10,
        "汉化": 8,
        "r18": 8,
        "无修": 6,
        "单行本": 6,
        "漫画": 5,
        "cg": 5,
    },
    "yandex": {
        "相似图": 10,
        "相似图片": 10,
        "找相似": 10,
        "像这个": 6,
        "类似的": 5,
        "照片": 4,
    },
    "google": {
        "找原图": 10,
        "综合搜索": 8,
        "以图搜图": 5,
        "新闻图": 5,
        "商品图": 5,
        "人脸": 3,
    },
}


class IntentRouter:
    """意图 → 引擎路由，支持多关键词加权匹配"""

    ANIME_IMAGE_KEYWORDS: ClassVar[list[str]] = [
        "角色",
        "动漫",
        "动画",
        "番",
        "二次元",
        "人物",
        "cos",
        "画师",
        "pixiv",
        "同人",
        "本子",
        "画风",
    ]

    @staticmethod
    def match(intent: str | None = None) -> str:
        """根据意图文本返回推荐引擎名

        参数:
            intent: 用户/LLM 提供的意图文本

        返回:
            str: 引擎名
        """
        if not intent:
            return "animetrace"  # 默认

        intent_lower = intent.lower()
        scores: dict[str, int] = {}

        for engine, keywords in INTENT_KEYWORD_WEIGHTS.items():
            score = 0
            for kw, weight in keywords.items():
                if kw in intent_lower:
                    score += weight
            if score > 0:
                scores[engine] = score

        if not scores:
            return "animetrace"

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    @classmethod
    def looks_anime(cls, intent: str | None = None) -> bool:
        """快速判断意图是否偏向二次元"""
        if not intent:
            return True
        return any(kw in intent.lower() for kw in cls.ANIME_IMAGE_KEYWORDS)


# ── 引擎名标准化 ────────────────────────────────────────


def resolve_engine_name(
    keyword: str, engine_keywords: dict[str, str] | None = None
) -> str | None:
    """将用户输入的关键词/别名解析为标准引擎名

    参数:
        keyword: 用户输入的引擎名或关键词
        engine_keywords: 自定义关键词→引擎名的映射

    返回:
        str | None: 标准引擎名，无法匹配则 None
    """
    key = keyword.lower().strip()

    # 1. 精确匹配引擎名
    if key in ENGINE_REGISTRY:
        return key

    # 2. 用户自定义关键词
    if engine_keywords:
        for kw, eng in engine_keywords.items():
            if kw.lower().strip() == key:
                if eng in ENGINE_REGISTRY:
                    return eng

    # 3. 模糊匹配（取前几个字符）
    for name in ENGINE_REGISTRY:
        if name.startswith(key) or key in name:
            return name

    return None


# ── 请求类注入 ──────────────────────────────────────────


def inject_request_classes():
    """将 api_request 模块的请求类注入到 ENGINE_REGISTRY
    延迟导入以避免循环依赖
    """
    from .utils.api_request import AnimeTrace, EHentai, GoogleLens, SauceNAO, Yandex

    ENGINE_REGISTRY["animetrace"].req_class = AnimeTrace
    ENGINE_REGISTRY["yandex"].req_class = Yandex
    ENGINE_REGISTRY["ehentai"].req_class = EHentai
    ENGINE_REGISTRY["google"].req_class = GoogleLens
    ENGINE_REGISTRY["saucenao"].req_class = SauceNAO
