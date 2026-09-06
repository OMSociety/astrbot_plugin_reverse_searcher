"""搜图 LLM 工具

提供自然语言搜图的能力：
- 通用搜图（自动判断引擎）
- 指定引擎搜图

芙兰会根据图片内容和对话意图自主选择最合适的搜索引擎。
"""

from __future__ import annotations

import asyncio

from astrbot.api import logger
from astrbot.api.message_components import Image as AstrImage
from astrbot.api.message_components import Reply
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass

from ..engine_registry import IntentRouter
from ..utils.security import is_safe_image_ref

# ============ 图片提取（两个 tool 共用）=============


def _extract_image_from_context(
    context: ContextWrapper[AstrAgentContext],
) -> tuple[str | None, str | None]:
    """从当前消息上下文提取图片引用，返回 (base64, url)。

    读 AstrBot 标准组件链：直发图片取第一个 Image 组件的 url/file
    （Image.fromURL 把 URL 存在 file 字段，两者都查）；引用回复从
    Reply.chain 中取（aiocqhttp 适配器 get_reply=True 时自动填充）。
    URL 安全性由调用方 is_safe_image_ref 校验。
    """
    url_str = None
    event = (
        getattr(context.context, "event", None) if hasattr(context, "context") else None
    )
    msg_obj = getattr(event, "message_obj", None) if event else None
    if not msg_obj:
        return None, None

    def _img_ref(comp) -> str:
        return getattr(comp, "url", "") or getattr(comp, "file", "") or ""

    for component in getattr(msg_obj, "message", []) or []:
        if isinstance(component, AstrImage):
            ref = _img_ref(component)
            if ref:
                url_str = ref
                break
    if not url_str:
        for component in getattr(msg_obj, "message", []) or []:
            if isinstance(component, Reply):
                for comp in component.chain or []:
                    if isinstance(comp, AstrImage):
                        ref = _img_ref(comp)
                        if ref:
                            url_str = ref
                            break
                if url_str:
                    break
    return None, url_str


async def _perform_search(
    search_model, engine: str, base64_str: str | None, url_str: str | None
) -> str | None:
    """执行搜索，统一处理 base64/URL 参数"""
    if base64_str:
        return await search_model.search(api=engine, base64=base64_str)
    elif url_str:
        return await search_model.search(api=engine, url=url_str)
    else:
        raise ValueError("No image provided")


def _format_search_result(result: str | None, engine: str) -> str:
    """格式化搜索结果为文本（search() 返回 str | None）"""
    from ..engine_registry import ENGINE_REGISTRY

    engine_def = ENGINE_REGISTRY.get(engine)
    label = engine_def.label if engine_def else engine

    if result is None or not result.strip():
        return f"🔍 [{label}] 未找到结果"
    return f"🔍 [{label}]\n{result[:500]}"


# ============ 基类 ============


@dataclass(config={"arbitrary_types_allowed": True})
class _BaseSearchTool(FunctionTool[AstrAgentContext]):
    """搜图工具基类，定义搜索流程模板"""

    description: str = ""
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "image_base64": {
                    "type": "string",
                    "description": "图片的 base64 编码（不含 data:image 前缀）",
                },
                "image_url": {
                    "type": "string",
                    "description": "或直接提供图片 URL（二选一，与 base64 互斥）",
                },
                "intent": {
                    "type": "string",
                    "description": "搜索意图，用于自动选引擎。例如：「找角色」「找出处」「找相似图」",
                },
            },
            "required": [],
        }
    )

    def __init__(self, **data):
        super().__init__(**data)
        self.search_model = None

    def inject_search_model(self, search_model):
        self.search_model = search_model

    async def _do_search(
        self,
        engine: str,
        base64_str: str | None,
        url_str: str | None,
    ) -> str:
        """执行搜索并格式化结果"""
        logger.info(
            f"[reverse_search] engine={engine}, url={url_str[:50] if url_str else 'base64'}"
        )
        result = await _perform_search(self.search_model, engine, base64_str, url_str)
        return _format_search_result(result, engine)

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> str:
        if not self.search_model:
            return "搜图引擎未初始化，请联系管理员"

        # 1. 提取图片
        base64_str = kwargs.get("image_base64") or kwargs.get("base64")
        url_str = kwargs.get("image_url") or kwargs.get("url")

        # SSRF/本地文件读取防护：LLM 传入的 URL 必须为公网图片地址（DNS 放线程池）
        if url_str and not await asyncio.to_thread(is_safe_image_ref, url_str):
            return "图片地址不安全：仅支持公网图片 URL 或消息内图片（已拒绝内网地址与本地文件）。"

        if not base64_str and not url_str:
            base64_str, url_str = await asyncio.to_thread(
                _extract_image_from_context, context
            )

        if not base64_str and not url_str:
            return "未找到图片。请附上图片再调用此工具。"

        # 2. 决定引擎（子类覆盖）
        engine = await self._resolve_engine(context, kwargs, base64_str, url_str)
        if not engine:
            return "无法确定搜索引擎"

        # 3. 搜索
        try:
            text = await self._do_search(engine, base64_str, url_str)
            return text
        except Exception as e:
            logger.error(f"[reverse_search] Error: {e}")
            return f"搜索出错：{e}"

    async def _resolve_engine(
        self,
        context: ContextWrapper[AstrAgentContext],
        kwargs: dict,
        base64_str: str | None,
        url_str: str | None,
    ) -> str | None:
        """解析引擎，由子类实现。返回引擎名或 None"""
        raise NotImplementedError


# ============ 通用搜图工具 ============


@dataclass(config={"arbitrary_types_allowed": True})
class ReverseSearchTool(_BaseSearchTool):
    """通用搜图工具 — 自动判断引擎"""

    name: str = "reverse_search"
    description: str = """以图搜图工具。当你想知道图片里的角色是谁、找出处、找相似图、找原图时调用。

【引擎选择建议】
- 想了解角色/人物 → animetrace（动漫角色识别最强，返回作品名+角色名）
- 想找出处/来源/画师 → saucenao（综合出处搜索，返回作者+链接）
- 想搜同人本/R18内容 → ehentai
- 想找相似图片 → yandex
- 想找原图/综合搜索 → google

芙兰应根据图片内容和对话意图自主选择引擎，不必每次都问用户。"""

    async def _resolve_engine(
        self,
        context: ContextWrapper[AstrAgentContext],
        kwargs: dict,
        base64_str: str | None,
        url_str: str | None,
    ) -> str | None:
        intent = kwargs.get("intent")
        return IntentRouter.match(intent)


@dataclass(config={"arbitrary_types_allowed": True})
class ReverseSearchWithEngineTool(_BaseSearchTool):
    """指定引擎搜图工具"""

    name: str = "reverse_search_with_engine"
    description: str = (
        "指定搜索引擎进行以图搜图。当用户明确要求使用某个特定引擎时调用。引擎参数必填。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "image_base64": {
                    "type": "string",
                    "description": "图片的 base64 编码",
                },
                "image_url": {
                    "type": "string",
                    "description": "或图片 URL",
                },
                "engine": {
                    "type": "string",
                    "description": "搜索引擎名称",
                    "enum": ["animetrace", "saucenao", "ehentai", "google", "yandex"],
                },
            },
            "required": ["engine"],
        }
    )

    async def _resolve_engine(
        self,
        context: ContextWrapper[AstrAgentContext],
        kwargs: dict,
        base64_str: str | None,
        url_str: str | None,
    ) -> str | None:
        engine = kwargs.get("engine")
        if not engine:
            return None
        return engine


# ============ 注册函数 ============


def register_search_tools(plugin_instance):
    """注册搜图工具到 AstrBot"""
    reverse_tool = ReverseSearchTool()
    with_engine_tool = ReverseSearchWithEngineTool()

    reverse_tool.inject_search_model(plugin_instance.search_model)
    with_engine_tool.inject_search_model(plugin_instance.search_model)

    plugin_instance.context.add_llm_tools(
        reverse_tool,
        with_engine_tool,
    )

    logger.info(
        "[ReverseSearcher] 搜图工具已注册：reverse_search, reverse_search_with_engine"
    )
