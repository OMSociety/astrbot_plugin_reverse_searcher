"""图片收集器

从消息事件中提取图片，统一接口：
1. 消息组件（Image 组件）
2. raw_message（OneBot dict 格式）
3. 引用消息（调用 get_msg API）

返回统一为 List[io.BytesIO]
"""
from __future__ import annotations

import io
import re
from typing import List

import httpx
from astrbot.api import logger

try:
    from astrbot.api.event import AstrMessageEvent
except ImportError:
    AstrMessageEvent = object


IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}


class ImageCollector:
    """图片收集器"""

    def __init__(self, get_msg_api_callable=None):
        """
        参数:
            get_msg_api_callable: 可选，用于获取被引用消息的 API 调用
        """
        self.get_msg_api = get_msg_api_callable

    async def collect_from_event(self, event: AstrMessageEvent) -> List[io.BytesIO]:
        """从消息事件收集所有图片"""
        images: List[io.BytesIO] = []

        images.extend(self._from_message_components(event))
        images.extend(self._from_raw_message(event))

        reply_id = self._extract_reply_id(event)
        if reply_id and not images:
            images.extend(await self._from_reply_message(event, reply_id))

        return images

    def _from_message_components(self, event: AstrMessageEvent) -> List[io.BytesIO]:
        """从消息组件提取图片"""
        images: List[io.BytesIO] = []
        if not hasattr(event, 'message_obj'):
            return images

        for comp in getattr(event.message_obj, 'message', []):
            comp_str = str(comp)
            if "type='Image'" in comp_str or "type='image'" in comp_str:
                url_match = re.search(r"url='([^']+)'", comp_str)
                if url_match:
                    url = url_match.group(1)
                    img = self._download_image(url)
                    if img:
                        images.append(img)
        return images

    def _from_raw_message(self, event: AstrMessageEvent) -> List[io.BytesIO]:
        """从 raw_message（OneBot 格式）提取图片"""
        images: List[io.BytesIO] = []
        raw_message = getattr(event, 'raw_message', {})
        if not isinstance(raw_message, dict):
            return images

        message_list = raw_message.get("message", [])
        if not isinstance(message_list, list):
            return images

        for seg in message_list:
            if not isinstance(seg, dict):
                continue
            if seg.get("type") != "image":
                continue
            data = seg.get("data", {})
            if not isinstance(data, dict):
                continue
            url = data.get("url") or data.get("file")
            if url:
                img = self._download_image(url)
                if img:
                    images.append(img)
        return images

    async def _from_reply_message(
        self, event: AstrMessageEvent, reply_id: str
    ) -> List[io.BytesIO]:
        """从被引用消息提取图片（需要 API）"""
        images: List[io.BytesIO] = []
        if not self.get_msg_api:
            return images

        try:
            result = await self.get_msg_api(message_id=int(reply_id))
        except Exception as e:
            logger.warning(f"通过 API 获取被引用消息失败: {e}")
            return images

        if not result:
            return images

        message_content = None
        if isinstance(result, dict):
            message_content = result.get('message', [])
        elif hasattr(result, 'message'):
            message_content = result.message
        else:
            return images

        if not message_content:
            return images

        for seg in message_content:
            seg_type = None
            data = None
            if isinstance(seg, dict):
                seg_type = seg.get('type')
                data = seg.get('data', {})
            elif hasattr(seg, 'type'):
                seg_type = seg.type
                data = getattr(seg, 'data', {})

            if seg_type == 'image':
                url = None
                if isinstance(data, dict):
                    url = data.get('url') or data.get('file')
                elif hasattr(data, 'url'):
                    url = data.url
                if url:
                    img = self._download_image(url)
                    if img:
                        images.append(img)

        return images

    def _extract_reply_id(self, event: AstrMessageEvent) -> str | None:
        """提取被引用消息的 ID"""
        raw_evt = getattr(event, 'raw_event', None)
        if not isinstance(raw_evt, dict):
            return None

        msg_segs = raw_evt.get('message', [])
        if isinstance(msg_segs, list):
            for seg in msg_segs:
                if seg.get('type') == 'reply':
                    return seg.get('data', {}).get('id')
        return None

    async def _download_image_async(self, url: str) -> io.BytesIO | None:
        """异步下载图片"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return io.BytesIO(resp.content)
        except Exception:
            pass
        return None

    def _download_image(self, url: str) -> io.BytesIO | None:
        """同步下载图片（兼容用）"""
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return io.BytesIO(resp.content)
        except Exception:
            pass
        return None
