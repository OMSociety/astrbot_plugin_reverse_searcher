"""搜索结果卡片渲染器

纯 PIL 手绘结果卡片，无外部依赖。
支持渐变顶栏、圆角缩略图、相似度进度条。
"""
from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..engine_registry import ENGINE_REGISTRY


# ── 字体 ────────────────────────────────────────────────

def _load_fonts() -> tuple:
    """加载中文字体，回退到默认字体"""
    try:
        from pathlib import Path
        base_dir = Path(__file__).parent.parent
        font_path = str(base_dir / "resource/font/arialuni.ttf")
        small = ImageFont.truetype(font_path, 14)
        body = ImageFont.truetype(font_path, 16)
        title = ImageFont.truetype(font_path, 20)
        header = ImageFont.truetype(font_path, 18)
        return small, body, title, header
    except Exception:
        small = body = title = header = ImageFont.load_default()
        return small, body, title, header


# ── 辅助函数 ────────────────────────────────────────────

def _hex_to_rgb(hex_str: str) -> tuple:
    h = hex_str.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _blend_colors(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def _rounded_mask(size: tuple, radius: int) -> Image.Image:
    """生成圆角矩形 alpha mask"""
    w, h = size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
    return mask


def _draw_gradient_rect(draw, xy: tuple, color1: tuple, color2: tuple):
    """从上到下渐变矩形"""
    x1, y1, x2, y2 = xy
    height = y2 - y1
    for y in range(height):
        t = y / max(height - 1, 1)
        color = _blend_colors(color1, color2, t)
        draw.line([(x1, y1 + y), (x2, y1 + y)], fill=color)


def _draw_similarity_bar(
    draw,
    x: int,
    y: int,
    width: int,
    similarity: float,
    font: ImageFont.ImageFont,
    text_color: tuple,
) -> None:
    """画相似度百分比进度条"""
    bar_height = 6
    bar_bg = (220, 220, 220)
    if similarity >= 90:
        bar_color = (76, 175, 80)   # 绿
    elif similarity >= 70:
        bar_color = (255, 193, 7)   # 黄
    else:
        bar_color = (244, 67, 54)   # 红

    draw.rounded_rectangle([x, y, x + width, y + bar_height], radius=3, fill=bar_bg)
    fill_w = int(width * min(similarity, 100) / 100)
    if fill_w > 0:
        draw.rounded_rectangle([x, y, x + fill_w, y + bar_height], radius=3, fill=bar_color)

    text = f"{similarity:.1f}%"
    if hasattr(font, "getbbox"):
        tw = font.getbbox(text)[2]
    else:
        tw = font.getsize(text)[0]
    draw.text((x + width + 8, y - 2), text, font=font, fill=text_color)


# ── 主渲染器 ────────────────────────────────────────────

class ResultCardRenderer:
    """手绘搜索结果卡片"""

    CARD_WIDTH = 900
    PADDING = 20
    THUMB_W = 150
    THUMB_H = 110
    ROW_HEIGHT = 120
    HEADER_H = 55
    SOURCE_H = 130

    def __init__(self):
        self.small, self.body, self.title, self.header = _load_fonts()

    def render(
        self,
        engine: str,
        results: list[dict],
        source_image: Optional[Image.Image] = None,
    ) -> Image.Image:
        """渲染结果卡片"""
        total_height = self._calc_height(results, source_image)
        canvas = Image.new('RGB', (self.CARD_WIDTH, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        self._draw_header(draw, engine, len(results))

        y = self.PADDING + self.HEADER_H
        if source_image:
            y = self._draw_source_thumb(canvas, source_image)

        y += self.PADDING
        for i, item in enumerate(results[:5]):
            y = self._draw_result_row(draw, canvas, i + 1, item, y)
            if i < len(results) - 1 and i < 4:
                y += 10

        return canvas

    def _calc_height(
        self,
        results: list,
        source_image: Optional[Image.Image],
    ) -> int:
        h = self.PADDING
        h += self.HEADER_H
        if source_image:
            h += self.SOURCE_H + self.PADDING
        h += self.PADDING
        h += (self.ROW_HEIGHT + 10) * min(len(results), 5)
        h += self.PADDING
        return h

    def _draw_header(self, draw: ImageDraw.Draw, engine: str, count: int) -> None:
        """绘制渐变顶栏（用文字图标替代 emoji）"""
        engine_def = ENGINE_REGISTRY.get(engine, None)
        if engine_def:
            base_color = _hex_to_rgb(
                f"#{engine_def.color[0]:02x}{engine_def.color[1]:02x}{engine_def.color[2]:02x}"
            )
        else:
            base_color = _hex_to_rgb("4a6ea9")
        title_color = _blend_colors(base_color, (30, 30, 60), 0.3)

        _draw_gradient_rect(
            draw, (0, 0, self.CARD_WIDTH, self.HEADER_H), base_color, title_color
        )

        label = engine_def.label if engine_def else engine.upper()
        text = f"[{label}] 搜索结果  {count} 条"
        if hasattr(draw, "textlength"):
            tw = draw.textlength(text, font=self.title)
        else:
            tw = self.title.getsize(text)[0]
        draw.text(((self.CARD_WIDTH - tw) // 2, 15), text, font=self.title, fill=(255, 255, 255))

    def _draw_source_thumb(self, canvas: Image.Image, source: Image.Image) -> int:
        """绘制源图缩略图"""
        src = source.copy()
        src.thumbnail((self.THUMB_W, self.THUMB_H), Image.LANCZOS)
        x = self.PADDING
        y = self.PADDING + self.HEADER_H + self.PADDING

        thumb_w, thumb_h = src.size
        rounded = src.copy().convert("RGBA")
        mask = _rounded_mask((thumb_w, thumb_h), 8)
        rounded.putalpha(mask)

        bg = Image.new("RGB", (thumb_w, thumb_h), (245, 245, 245))
        bg.paste(rounded, mask=255)
        canvas.paste(bg, (x, y))

        draw = ImageDraw.Draw(canvas)
        draw.text((x, y + thumb_h + 4), "[Source]", font=self.small, fill=(120, 120, 120))

        return y + thumb_h + 4 + 18

    def _draw_result_row(
        self,
        draw: ImageDraw.Draw,
        canvas: Image.Image,
        index: int,
        item: dict,
        y: int,
    ) -> int:
        """绘制单条结果行"""
        x_text = self.PADDING + self.THUMB_W + 15

        # 分隔线
        draw.line(
            [(self.PADDING, y), (self.CARD_WIDTH - self.PADDING, y)],
            fill=(230, 230, 230), width=1,
        )
        y += 8

        # 来源
        source = item.get("source", "未知来源")
        draw.text((x_text, y), f"{index}. {source}", font=self.body, fill=(40, 40, 40))
        y += 20

        # 标题
        title_text = item.get("title", "")
        if title_text:
            draw.text((x_text, y), f"   {title_text}", font=self.small, fill=(80, 80, 80))
            y += 18

        # 画师
        author = item.get("author", "")
        if author:
            draw.text((x_text, y), f"   {author}", font=self.small, fill=(100, 100, 100))
            y += 18

        # 相似度条
        sim_str = item.get("similarity", "")
        if sim_str:
            try:
                similarity = float(sim_str.replace("%", "").replace("\uff05", ""))
            except Exception:
                similarity = 0
            if similarity > 0:
                _draw_similarity_bar(draw, x_text, y, 120, similarity, self.small, (60, 60, 60))
                y += 20

        # 链接
        url = item.get("url", "")
        if url:
            short_url = url[:70] + "..." if len(url) > 70 else url
            draw.text((x_text, y), f"   {short_url}", font=self.small, fill=(41, 98, 255))
            y += 18

        return y + 10

    def render_error(self, engine: str, error_msg: str) -> Image.Image:
        """绘制错误提示图"""
        w, h = self.CARD_WIDTH, 180
        canvas = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        engine_def = ENGINE_REGISTRY.get(engine, None)
        if engine_def:
            err_color = _hex_to_rgb(
                f"#{engine_def.color[0]:02x}{engine_def.color[1]:02x}{engine_def.color[2]:02x}"
            )
        else:
            err_color = (231, 76, 60)

        draw.rectangle([(0, 0), (w, self.HEADER_H)], fill=err_color)
        label = engine_def.label if engine_def else engine.upper()
        draw.text(
            (self.PADDING, 15),
            f"[{label}] 搜索失败",
            font=self.title,
            fill=(255, 255, 255),
        )

        draw.text(
            (self.PADDING, 80),
            f"Error: {error_msg}",
            font=self.body,
            fill=(80, 80, 80),
        )

        return canvas
