"""搜图 LLM 工具

提供自然语言搜图的能力：
- 通用搜图（自动判断引擎）
- 指定引擎搜图

芙兰会根据图片内容和用户意图自主选择最合适的搜索引擎。
"""
import io
from typing import Optional
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot import logger
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.agent.run_context import ContextWrapper


# ============ 引擎决策表 ============

ENGINE_MAP = {
    "animetrace": {
        "label": "AnimeTrace",
        "desc": "动漫角色识别",
        "fallback": ["saucenao"],
    },
    "saucenao": {
        "label": "SauceNAO",
        "desc": "综合出处搜索",
        "fallback": ["google"],
    },
    "ehentai": {
        "label": "E-Hentai",
        "desc": "同人本/汉化组",
        "fallback": [],
    },
    "google": {
        "label": "Google 图片",
        "desc": "综合搜索引擎",
        "fallback": ["yandex"],
    },
    "yandex": {
        "label": "Yandex",
        "desc": "相似图片搜索",
        "fallback": ["google"],
    },
}

# 意图关键词 → 推荐引擎
INTENT_ENGINE_TABLE = {
    "角色": "animetrace",
    "角色名": "animetrace",
    "是谁": "animetrace",
    "哪个人物": "animetrace",
    "动漫角色": "animetrace",
    "cos": "animetrace",
    "出处": "saucenao",
    "来源": "saucenao",
    "画师": "saucenao",
    "同人": "ehentai",
    "本子": "ehentai",
    "相似图": "yandex",
    "找原图": "google",
    "搜图": "auto",
}


def decide_engine(intent: Optional[str] = None, explicit_engine: Optional[str] = None) -> str:
    """根据意图或显式指定决定使用哪个引擎"""
    if explicit_engine:
        return explicit_engine
    
    if not intent:
        return "animetrace"  # 默认用 animetrace
    
    intent = intent.strip()
    # 精确匹配
    for key, engine in INTENT_ENGINE_TABLE.items():
        if key in intent:
            return engine
    return "animetrace"  # 无法判断时默认


def format_search_result(result: dict, engine: str) -> str:
    """格式化搜索结果为文本"""
    if isinstance(result, str):
        label = ENGINE_MAP.get(engine, {}).get("label", engine)
        return f"🔍 [{label}]\n{result[:500]}"
    
    images = result.get("images", [])
    extra_text = result.get("extra_text", "")
    error_msg = result.get("error", "")
    
    if error_msg:
        return f"❌ [{ENGINE_MAP.get(engine, {}).get('label', engine)}] 搜索失败：{error_msg}"
    
    if not images:
        return f"🔍 [{ENGINE_MAP.get(engine, {}).get('label', engine)}] 未找到结果"
    
    label = ENGINE_MAP.get(engine, {}).get("label", engine)
    lines_out = [f"🔍 [{label}] 找到 {len(images)} 个结果"]
    
    for i, img in enumerate(images[:5], 1):
        source = img.get("source", "未知来源")
        similarity = img.get("similarity", "")
        img_url = img.get("url", "")
        
        lines_out.append(f"\n{i}. {source}")
        if similarity:
            lines_out.append(f"   📊 相似度: {similarity}")
        if img_url:
            lines_out.append(f"   🔗 {img_url[:80]}")
    
    if extra_text:
        lines_out.append(f"\n📝 {extra_text}")
    
    return "\n".join(lines_out)

    def __init__(self, **data):
        super().__init__(**data)
        self.search_model = None

    def inject_search_model(self, search_model):
        """注入搜索模型"""
        self.search_model = search_model

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs):
        if not self.search_model:
            return ToolExecResult("搜图引擎未初始化，请联系管理员")
        
        base64 = kwargs.get("image_base64") or kwargs.get("base64")
        url = kwargs.get("image_url") or kwargs.get("url")
        explicit_engine = kwargs.get("engine")
        intent = kwargs.get("intent")
        
        # 尝试从上下文获取图片
        if not base64 and not url:
            # 方法1: 从 message.image_list 获取（兼容旧格式）
            msg = getattr(context.context, 'message', None) or                   (context.context.event.message_obj if hasattr(context.context, 'event') else None)
            if msg and hasattr(msg, 'image_list') and msg.image_list:
                url = msg.image_list[0]
            # 方法2: 从 context.messages 获取最新用户消息中的图片
            elif hasattr(context.context, 'messages'):
                from astrbot.core.agent.message import UserMessageSegment
                for msg_seg in reversed(context.context.messages):
                    if isinstance(msg_seg, UserMessageSegment):
                        for part in msg_seg.content:
                            if part.type == "image_url":
                                url = part.image_url.get("url", "") if isinstance(part.image_url, dict) else str(part.image_url)
                                break
                        if url:
                            break
            # 方法3: 从 event.message_obj.content 中正则匹配
            if not url and hasattr(context.context, 'event'):
                event = context.context.event
                if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'content'):
                    import re
                    img_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)', event.message_obj.content)
                    if img_matches:
                        url = img_matches[0]
        
        if not base64 and not url:
            return ToolExecResult("未找到图片。请附上图片再调用此工具。")
        
        # 决定引擎
        chosen_engine = decide_engine(intent, explicit_engine)
        logger.info(f"[reverse_search] engine={chosen_engine}, intent={intent}, url={url[:50] if url else 'base64'}")
        
        try:
            if base64:
                result = await self.search_model.search(api=chosen_engine, base64=base64)
            else:
                result = await self.search_model.search(api=chosen_engine, url=url)
            
            text = format_search_result(result, chosen_engine)
            return ToolExecResult(text)
        except Exception as e:
            logger.error(f"[reverse_search] Error: {e}")
            return ToolExecResult(f"搜索出错：{str(e)}")


@dataclass(config=dict(arbitrary_types_allowed=True))
class ReverseSearchWithEngineTool(FunctionTool[AstrAgentContext]):
    """指定引擎搜图工具
    
    当用户明确要求使用某个搜索引擎时调用。
    一般情况下建议用 reverse_search（自动选引擎）。
    """
    
    name: str = "reverse_search_with_engine"
    description: str = "指定搜索引擎进行以图搜图。当用户明确要求使用某个特定引擎时调用。引擎参数必填。"
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

    def __init__(self, **data):
        super().__init__(**data)
        self.search_model = None

    def inject_search_model(self, search_model):
        self.search_model = search_model

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs):
        if not self.search_model:
            return ToolExecResult("搜图引擎未初始化，请联系管理员")
        
        base64 = kwargs.get("image_base64") or kwargs.get("base64")
        url = kwargs.get("image_url") or kwargs.get("url")
        engine = kwargs.get("engine")
        
        if not base64 and not url:
            msg = getattr(context.context, 'message', None) or                   (context.context.event.message_obj if hasattr(context.context, 'event') else None)
            if msg and hasattr(msg, 'image_list') and msg.image_list:
                url = msg.image_list[0]
            elif hasattr(context.context, 'messages'):
                from astrbot.core.agent.message import UserMessageSegment
                for msg_seg in reversed(context.context.messages):
                    if isinstance(msg_seg, UserMessageSegment):
                        for part in msg_seg.content:
                            if part.type == "image_url":
                                url = part.image_url.get("url", "") if isinstance(part.image_url, dict) else str(part.image_url)
                                break
                        if url:
                            break
            if not url and hasattr(context.context, 'event'):
                event = context.context.event
                if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'content'):
                    import re
                    img_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)', event.message_obj.content)
                    if img_matches:
                        url = img_matches[0]
        
        if not base64 and not url:
            return ToolExecResult("未找到图片。请附上图片再调用此工具。")
        
        if not engine:
            return ToolExecResult("请指定 engine 参数（animetrace/saucenao/ehentai/google/yandex）")
        
        logger.info(f"[reverse_search_with_engine] engine={engine}, url={url[:50] if url else 'base64'}")
        
        try:
            if base64:
                result = await self.search_model.search(api=engine, base64=base64)
            else:
                result = await self.search_model.search(api=engine, url=url)
            
            text = format_search_result(result, engine)
            return ToolExecResult(text)
        except Exception as e:
            logger.error(f"[reverse_search_with_engine] Error: {e}")
            return ToolExecResult(f"搜索出错：{str(e)}")


# ============ 注册函数 ============

def register_search_tools(plugin_instance):
    """注册搜图工具到 AstrBot"""
    reverse_tool = ReverseSearchTool()
    with_engine_tool = ReverseSearchWithEngineTool()
    
    # 注入搜索模型（从插件实例获取）
    reverse_tool.inject_search_model(plugin_instance.search_model)
    with_engine_tool.inject_search_model(plugin_instance.search_model)
    
    # 注册到 AstrBot
    plugin_instance.context.add_llm_tools(
        reverse_tool,
        with_engine_tool,
    )
    
    logger.info("[ReverseSearcher] 搜图工具已注册：reverse_search, reverse_search_with_engine")