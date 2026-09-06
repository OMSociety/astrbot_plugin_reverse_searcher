"""消息内容提取：标准组件链优先，旧版 raw_message 正则兜底。

QQ 官方等平台的 raw_message 是 SDK 对象，旧正则逻辑无法提取，
因此优先走 AstrBot 标准字段/组件链；旧逻辑仅作极老版本适配器兜底。
"""

from __future__ import annotations

import os
import re

from astrbot.api.message_components import Image as AstrImage


def get_img_urls(message) -> str:
    """
    从消息对象中提取第一张图片的URL

    优先使用 AstrBot 标准消息组件链（跨平台统一），
    旧版 raw_message 正则逻辑保留作兜底。

    参数:
        message: 消息体对象，可含message或raw_message属性

    返回:
        str: 图片URL，如果没有找到则返回空字符串

    异常:
        无
    """
    # AstrBot 标准组件链（QQ 官方等平台的 raw_message 是 SDK 对象，正则提取不到）
    # 注意：Image.fromURL 把 URL 存在 file 字段（url 字段为空），需同时检查两者
    for component in getattr(message, "message", []) or []:
        if isinstance(component, AstrImage):
            img_ref = (
                getattr(component, "url", "") or getattr(component, "file", "") or ""
            )
            if img_ref:
                return img_ref
    # 旧逻辑兜底
    raw_message = getattr(message, "raw_message", "")
    if isinstance(raw_message, dict) and "message" in raw_message:
        raw_message_str = str(raw_message.get("message", []))
        image_match = re.search(
            r"'type':\s*'image'.*?'url':\s*'([^']+)'", raw_message_str
        )
        if image_match:
            return image_match.group(1)
        file_match = re.search(
            r"'type':\s*'file'.*?'file':\s*'([^']+)'", raw_message_str
        )
        if file_match:
            filename = file_match.group(1)
            IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
            if os.path.splitext(filename.lower())[1] in IMAGE_EXTS:
                for component in getattr(message, "message", []):
                    component_str = str(component)
                    if "type='File'" in component_str:
                        url_match = re.search(r"url='([^']+)'", component_str)
                        if url_match:
                            return url_match.group(1)
    return ""


def get_message_text(message) -> str:
    """
    提取消息对象中的文本内容（忽略图片和其他非文本消息段落）

    优先使用 AstrBot 标准 message_str 字段（所有平台适配器统一填充；
    QQ 官方等平台的 raw_message 是 SDK 对象，旧正则逻辑无法提取），
    旧逻辑保留作兜底。

    参数:
        message: 消息体对象

    返回:
        str: 提取到的文本内容（去首尾空格）

    异常:
        无
    """
    # AstrBot 标准纯文本字段（跨平台统一）
    message_str = getattr(message, "message_str", "")
    if isinstance(message_str, str) and message_str.strip():
        return message_str.strip()
    # 旧逻辑兜底
    raw_message = getattr(message, "raw_message", "")
    if isinstance(raw_message, str):
        return raw_message.strip()
    elif isinstance(raw_message, dict) and "message" in raw_message:
        texts = [
            (
                msg_part.get("data", {}).get("text", "")
                if isinstance(msg_part, dict)
                else str(msg_part)
            )
            for msg_part in raw_message.get("message", [])
            if (isinstance(msg_part, dict) and msg_part.get("type") == "text")
            or isinstance(msg_part, str)
        ]
        return " ".join(texts).strip()
    return ""
