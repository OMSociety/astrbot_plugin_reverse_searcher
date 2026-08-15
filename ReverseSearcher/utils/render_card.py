"""搜索结果卡片渲染器

主路径：HTML 模板 + AstrBot 文转图（云端 t2i）。
风格参考 astrbot.app（天蓝 #3c96ca 渐变 Header + 白色圆角卡片 + 柔和阴影）。
源图/结果缩略图由本模块转 base64 data URI 内嵌（云端渲染器访问不了本地/外链）。

回退：云端 t2i 不可达/超时（25s）时降级为 PIL 手绘文字卡片（内置 NotoSansSC 字体）。
"""

from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from astrbot.api import logger
from astrbot.core import html_renderer

from ..engine_registry import ENGINE_REGISTRY
from .templates import ERROR_TMPL, RESULT_CARD_TMPL

# HTML 渲染最长等待（秒）：超时降级 PIL，避免拖慢整个搜索流程
HTML_RENDER_TIMEOUT = 25


# ── 字体（PIL 回退用，懒加载单例）──────────────────────────


_font_cache = None


def _load_fonts() -> tuple:
    """加载插件内置中文字体（模块级懒加载单例）"""
    global _font_cache
    if _font_cache is not None:
        return _font_cache
    try:
        base_dir = Path(__file__).parent.parent
        regular_font = str(base_dir / "resource/font/NotoSansSC-Regular.otf")

        small = ImageFont.truetype(regular_font, 16)
        body = ImageFont.truetype(regular_font, 18)
        title = ImageFont.truetype(regular_font, 26)
        header_font = ImageFont.truetype(regular_font, 20)
        mono = ImageFont.truetype(regular_font, 14)
        _font_cache = (small, body, title, header_font, mono)
        return _font_cache
    except Exception:
        d = ImageFont.load_default()
        _font_cache = (d, d, d, d, d)
        return _font_cache


# ── 辅助函数 ──────────────────────────────────────────────


def _engine_color_hex(engine: str) -> str:
    """引擎主题色（HEX），未知引擎用 AstrBot 天蓝"""
    engine_def = ENGINE_REGISTRY.get(engine)
    if engine_def:
        c = engine_def.color
        return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
    return "#3c96ca"


def _engine_label(engine: str) -> str:
    engine_def = ENGINE_REGISTRY.get(engine)
    return engine_def.label if engine_def else engine.upper()


def _sim_class(sim_str) -> str:
    """相似度 → 徽章样式（≥90 绿 / ≥70 橙 / >0 红 / 无 灰）"""
    try:
        s = float(str(sim_str).replace("%", "").replace("％", ""))
        if s >= 90:
            return "sim-high"
        if s >= 70:
            return "sim-mid"
        if s > 0:
            return "sim-low"
    except (ValueError, TypeError):
        pass
    return "sim-none"


def _img_to_data_uri(img: Image.Image | None, max_size: int = 400, quality: int = 80) -> str:
    """PIL 图片 → 压缩 → base64 data URI（内嵌 HTML，渲染不依赖外网）"""
    if img is None:
        return ""
    try:
        im = img.copy()
        im.thumbnail((max_size, max_size), Image.LANCZOS)
        if im.mode in ("RGBA", "P", "LA"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    except Exception:  # noqa: BLE001 - 单张图失败不影响整体
        return ""


# ── 主渲染器 ──────────────────────────────────────────────


class ResultCardRenderer:
    """搜索结果卡片渲染器（HTML 主路径 + PIL 回退）"""

    # ── HTML 主路径 ────────────────────────────────────────

    async def render_html_async(
        self,
        engine: str,
        results: list[dict],
        source_image: Image.Image | None = None,
        ai_detect: bool | None = None,
    ) -> str | None:
        """HTML 模板渲染，返回本地图片路径；失败/超时返回 None（调用方降级）"""
        data = {
            "engine_label": _engine_label(engine),
            "engine_color": _engine_color_hex(engine),
            "count": len(results),
            "ai_detect": ai_detect,
            "source_image_b64": _img_to_data_uri(source_image, max_size=400),
            "results": [
                {
                    "source": item.get("source") or "未知来源",
                    "title": item.get("title") or "",
                    "author": item.get("author") or "",
                    "similarity": item.get("similarity") or "",
                    "sim_class": _sim_class(item.get("similarity")),
                    "url": item.get("url") or "",
                    "thumbnail_b64": _img_to_data_uri(
                        item.get("thumbnail_image"), max_size=256
                    ),
                    "thumb_flat": self._thumb_is_flat(item),
                }
                for item in results[:5]
            ],
        }
        try:
            return await asyncio.wait_for(
                html_renderer.render_custom_template(
                    RESULT_CARD_TMPL,
                    data,
                    return_url=False,
                    options={"full_page": True, "type": "jpeg", "quality": 80},
                ),
                timeout=HTML_RENDER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[ReverseSearcher] HTML 卡片渲染超时（>{HTML_RENDER_TIMEOUT}s，云端 t2i 服务慢/不可达），降级 PIL"
            )
            return None
        except Exception as e:  # noqa: BLE001 - 渲染失败/超时降级 PIL
            logger.warning(
                f"[ReverseSearcher] HTML 卡片渲染失败（{type(e).__name__}: {e}），降级 PIL"
            )
            return None

    async def render_error_html_async(self, engine: str, error_msg: str) -> str | None:
        """错误提示卡片（HTML），返回图片路径；失败返回 None"""
        data = {
            "engine_label": _engine_label(engine),
            "engine_color": _engine_color_hex(engine),
            "error_msg": error_msg,
        }
        try:
            return await asyncio.wait_for(
                html_renderer.render_custom_template(
                    ERROR_TMPL,
                    data,
                    return_url=False,
                    options={"full_page": True, "type": "jpeg", "quality": 80},
                ),
                timeout=HTML_RENDER_TIMEOUT,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ReverseSearcher] 错误卡片 HTML 渲染失败，降级 PIL: {e}")
            return None

    # ── PIL 回退 ──────────────────────────────────────────

    CARD_WIDTH = 960
    CARD_PADDING = 24
    THUMB_SIZE = 160
    HEADER_H = 72
    ROW_PADDING_V = 20
    CARD_RADIUS = 12

    @staticmethod
    def _thumb_is_flat(item: dict) -> bool:
        thumb = item.get("thumbnail_image")
        if thumb and isinstance(thumb, Image.Image):
            return thumb.width > thumb.height
        return False

    def render_pil(
        self,
        engine: str,
        results: list[dict],
        source_image: Image.Image | None = None,
        ai_detect: bool | None = None,
    ) -> Image.Image:
        """PIL 手绘结果卡片（HTML 渲染不可用时的回退）"""
        self.small, self.body, self.title, self.header_font, self.mono = _load_fonts()
        engine_color = _hex_to_rgb(_engine_color_hex(engine))
        total_height = self._calc_height(results, source_image, ai_detect)
        bg_color = (248, 249, 250)
        canvas = Image.new("RGB", (self.CARD_WIDTH, total_height), bg_color)
        draw = ImageDraw.Draw(canvas)

        self._draw_header_pil(draw, engine, engine_color, len(results))

        y = self.CARD_PADDING + self.HEADER_H
        if ai_detect is not None:
            y = self._draw_ai_badge(draw, ai_detect, y)
        if source_image:
            y = self._draw_source_thumb(canvas, source_image, y)

        y += self.ROW_PADDING_V
        for i, item in enumerate(results[:5]):
            y = self._draw_result_card_pil(draw, canvas, i + 1, item, y, engine_color)
            y += self.ROW_PADDING_V

        return canvas

    def render_error_pil(self, engine: str, error_msg: str) -> Image.Image:
        """PIL 错误提示图（回退）"""
        self.small, self.body, self.title, self.header_font, self.mono = _load_fonts()
        w, h = self.CARD_WIDTH, 200
        canvas = Image.new("RGB", (w, h), (248, 249, 250))
        draw = ImageDraw.Draw(canvas)
        err_color = _hex_to_rgb(_engine_color_hex(engine))

        draw.rectangle([(0, 0), (w, self.HEADER_H)], fill=err_color)
        draw.text(
            (self.CARD_PADDING, 16),
            f"「{_engine_label(engine)}」搜索失败",
            font=self.title,
            fill=(255, 255, 255),
        )
        draw.text(
            (self.CARD_PADDING, 90),
            f"Error: {error_msg}",
            font=self.body,
            fill=(100, 100, 100),
        )
        return canvas

    def _calc_height(
        self,
        results: list,
        source_image: Image.Image | None,
        ai_detect: bool | None = None,
    ) -> int:
        h = self.HEADER_H
        if ai_detect is not None:
            h += 46
        if source_image:
            h += 180 + 12
        h += self.CARD_PADDING
        for item in results[:5]:
            h += self._row_height(item)
        h += self.ROW_PADDING_V * (min(len(results), 5) + 2)
        h += self.CARD_PADDING
        return h

    def _row_height(self, item: dict) -> int:
        thumb = item.get("thumbnail_image")
        if thumb and isinstance(thumb, Image.Image):
            ow, oh = thumb.size
            thumb_h = max(int(oh * self.THUMB_SIZE / ow), 60) if ow > oh else self.THUMB_SIZE
        else:
            thumb_h = 0

        text_lines = 1
        if item.get("title"):
            text_lines += 1
        if item.get("author"):
            text_lines += 1
        if item.get("similarity"):
            text_lines += 1
        text_h = text_lines * 26 + self.ROW_PADDING_V * 2

        return max(thumb_h + self.ROW_PADDING_V * 2, text_h, 72)

    def _draw_header_pil(self, draw, engine: str, color: tuple, count: int) -> None:
        draw.rectangle([(0, 0), (self.CARD_WIDTH, self.HEADER_H)], fill=color)
        text = f"「{_engine_label(engine)}」搜索结果 — {count} 条匹配"
        tw = draw.textlength(text, font=self.title)
        draw.text(
            ((self.CARD_WIDTH - tw) // 2, 18),
            text,
            font=self.title,
            fill=(255, 255, 255),
        )

    def _draw_ai_badge(self, draw, ai: bool, y: int) -> int:
        badge_w, badge_h = 220, 34
        x = self.CARD_PADDING
        badge_color = (255, 138, 101) if ai else (102, 187, 106)
        label = "⚠ AI 生成嫌疑" if ai else "✓ 非 AI 生成"
        draw.rounded_rectangle(
            [(x, y), (x + badge_w, y + badge_h)], radius=6, fill=badge_color
        )
        tw = draw.textlength(label, font=self.small)
        draw.text((x + (badge_w - tw) // 2, y + 7), label, font=self.small, fill=(255, 255, 255))
        return y + badge_h + 10

    def _draw_source_thumb(self, canvas: Image.Image, source: Image.Image, y: int) -> int:
        src = source.copy()
        src.thumbnail((240, 160), Image.LANCZOS)
        x = self.CARD_PADDING
        tw, th = src.size
        rounded = src.convert("RGBA")
        mask = _rounded_mask((tw, th), 10)
        rounded.putalpha(mask)
        card_w, card_h = tw + 12, th + 12
        card = Image.new("RGB", (card_w, card_h), (255, 255, 255))
        card_draw = ImageDraw.Draw(card)
        card_draw.rounded_rectangle(
            [(2, 2), (card_w - 1, card_h - 1)], radius=10, fill=(230, 230, 230)
        )
        card.paste(rounded, (6, 6), rounded)
        canvas.paste(card, (x, y))
        return y + card_h + 4

    def _draw_result_card_pil(
        self, draw, canvas: Image.Image, index: int, item: dict, y: int, engine_color: tuple
    ) -> int:
        card_x = self.CARD_PADDING
        card_w = self.CARD_WIDTH - self.CARD_PADDING * 2
        card_h = self._row_height(item)
        radius = self.CARD_RADIUS

        shadow_offset = 3
        draw.rounded_rectangle(
            [(card_x + shadow_offset, y + shadow_offset), (card_x + card_w + shadow_offset, y + card_h + shadow_offset)],
            radius=radius,
            fill=(200, 200, 208),
        )
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)], radius=radius, fill=(255, 255, 255)
        )
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)], radius=radius, outline=(215, 215, 222), width=1
        )
        draw.rectangle(
            [(card_x, y + radius), (card_x + 5, y + card_h - radius)], fill=engine_color
        )

        text_x = card_x + 5 + 16
        inner_y = y + self.ROW_PADDING_V

        thumb = item.get("thumbnail_image")
        if thumb and isinstance(thumb, Image.Image):
            th = thumb.copy()
            ow, oh = th.size
            if ow > oh:
                new_w = min(ow, self.THUMB_SIZE)
                new_h = max(int(oh * new_w / ow), 1)
            else:
                new_h = min(oh, self.THUMB_SIZE)
                new_w = max(int(ow * new_h / oh), 1)
            th = th.resize((new_w, new_h), Image.LANCZOS)
            th_rounded = th.convert("RGBA")
            th_mask = _rounded_mask((new_w, new_h), 8)
            th_rounded.putalpha(th_mask)
            th_x = card_x + card_w - self.CARD_PADDING - new_w
            th_y = inner_y + (card_h - self.ROW_PADDING_V * 2 - new_h) // 2
            canvas.paste(th_rounded, (th_x, th_y), th_rounded)

        text_y = inner_y + 6
        source = item.get("source", "未知来源")
        draw.text((text_x, text_y), source, font=self.body, fill=(30, 30, 30))
        text_y += 26

        title_text = item.get("title", "")
        if title_text:
            if len(title_text) > 36:
                title_text = title_text[:33] + "..."
            draw.text((text_x, text_y), title_text, font=self.small, fill=(90, 90, 90))
            text_y += 22

        author = item.get("author", "")
        if author:
            draw.text((text_x, text_y), f"作者: {author}", font=self.small, fill=(120, 120, 120))
            text_y += 22

        sim_str = item.get("similarity", "")
        if sim_str:
            try:
                similarity = float(str(sim_str).replace("%", "").replace("％", ""))
            except (ValueError, TypeError):
                similarity = 0
            if similarity > 0:
                _draw_similarity_bar(draw, text_x, text_y + 8, 200, similarity, self.small, (80, 80, 80))
                text_y += 26

        url = item.get("url", "")
        if url:
            short_url = url[:60] + "..." if len(url) > 60 else url
            draw.text((text_x, text_y), short_url, font=self.mono, fill=(41, 98, 255))

        return y + card_h


# ── PIL 辅助（回退用）─────────────────────────────────────


def _hex_to_rgb(hex_str: str) -> tuple:
    h = hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rounded_mask(size: tuple, radius: int) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
    return mask


def _draw_similarity_bar(draw, x, y, width, similarity, font, text_color) -> None:
    bar_h = 10
    radius = 5
    bg_color = (220, 220, 220)

    if similarity >= 90:
        bar_color = (76, 175, 80)
    elif similarity >= 70:
        bar_color = (255, 152, 0)
    else:
        bar_color = (244, 67, 54)

    draw.rounded_rectangle([x, y, x + width, y + bar_h], radius=radius, fill=bg_color)
    fill_w = int(width * min(similarity, 100) / 100)
    if fill_w > 0:
        draw.rounded_rectangle([x, y, x + fill_w, y + bar_h], radius=radius, fill=bar_color)

    text = f"{similarity:.1f}%"
    draw.text((x + width + 8, y - 7), text, font=font, fill=text_color)
