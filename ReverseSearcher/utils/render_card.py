"""搜索结果卡片渲染器

纯 PIL 手绘结果卡片，无外部依赖。
支持渐变顶栏、缩略图预览、相似度进度条、圆角卡片。
"""
from __future__ import annotations

from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..engine_registry import ENGINE_REGISTRY


# ── 字体 ────────────────────────────────────────────────

def _load_fonts() -> tuple:
    """加载插件内置中文字体"""
    try:
        from pathlib import Path
        base_dir = Path(__file__).parent.parent
        font_path = str(base_dir / "resource/font/NotoSansSC-Regular.otf")

        small = ImageFont.truetype(font_path, 13)
        body = ImageFont.truetype(font_path, 15)
        title = ImageFont.truetype(font_path, 22)
        header = ImageFont.truetype(font_path, 17)
        mono = ImageFont.truetype(font_path, 12)
        return small, body, title, header, mono
    except Exception:
        d = ImageFont.load_default()
        return d, d, d, d, d


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
    bar_h = 8
    radius = 4
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
    if hasattr(font, "getbbox"):
        tw = font.getbbox(text)[2]
    else:
        tw = font.getsize(text)[0]
    draw.text((x + width + 8, y - 1), text, font=font, fill=text_color)


# ── 主渲染器 ────────────────────────────────────────────

class ResultCardRenderer:
    """手绘搜索结果卡片"""

    CARD_WIDTH = 960
    CARD_PADDING = 24
    THUMB_SIZE = 100          # 缩略图正方形边长
    THUMB_GAP = 16            # 缩略图与文字间距
    HEADER_H = 60
    SOURCE_H = 140            # 源图区域高度
    CARD_RADIUS = 12
    ROW_PADDING_V = 14

    def __init__(self):
        self.small, self.body, self.title, self.header, self.mono = _load_fonts()

    def render(
        self,
        engine: str,
        results: list[dict],
        source_image: Optional[Image.Image] = None,
    ) -> Image.Image:
        """渲染结果卡片"""
        total_height = self._calc_height(results, source_image)
        bg_color = (248, 249, 250)
        canvas = Image.new('RGB', (self.CARD_WIDTH, total_height), bg_color)
        draw = ImageDraw.Draw(canvas)

        self._draw_header(draw, engine, len(results))

        y = self.CARD_PADDING + self.HEADER_H
        if source_image:
            y = self._draw_source_thumb(canvas, source_image, y)

        y += self.CARD_PADDING
        for i, item in enumerate(results[:5]):
            y = self._draw_result_card(draw, canvas, i + 1, item, y)
            y += self.ROW_PADDING_V

        return canvas

    def _calc_height(self, results: list, source_image: Optional[Image.Image]) -> int:
        h = self.CARD_PADDING
        h += self.HEADER_H
        if source_image:
            h += self.SOURCE_H
        h += self.CARD_PADDING
        for item in results[:5]:
            h += self._row_height(item)
        h += self.ROW_PADDING_V * min(len(results), 5)
        h += self.CARD_PADDING
        return h

    def _row_height(self, item: dict) -> int:
        """计算单行卡片高度"""
        base = self.THUMB_SIZE + self.ROW_PADDING_V * 2
        # 有作者/title 时略有增加
        if item.get('title'):
            base += 2
        if item.get('author'):
            base += 2
        return max(base, self.THUMB_SIZE + 40)

    def _draw_header(self, draw: ImageDraw.Draw, engine: str, count: int) -> None:
        """绘制渐变顶栏"""
        engine_def = ENGINE_REGISTRY.get(engine, None)
        if engine_def:
            base_color = _hex_to_rgb(
                f"#{engine_def.color[0]:02x}{engine_def.color[1]:02x}{engine_def.color[2]:02x}"
            )
        else:
            base_color = _hex_to_rgb("4a6ea9")
        dark_color = _blend_colors(base_color, (20, 20, 50), 0.35)

        _draw_gradient_rect(
            draw, (0, 0, self.CARD_WIDTH, self.HEADER_H), base_color, dark_color
        )

        label = engine_def.label if engine_def else engine.upper()
        text = f"「{label}」搜索结果 — {count} 条匹配"
        if hasattr(draw, "textlength"):
            tw = draw.textlength(text, font=self.title)
        else:
            tw = self.title.getsize(text)[0]
        draw.text(((self.CARD_WIDTH - tw) // 2, 16), text, font=self.title, fill=(255, 255, 255))

    def _draw_source_thumb(self, canvas: Image.Image, source: Image.Image, y: int) -> int:
        """绘制源图缩略图"""
        src = source.copy()
        src.thumbnail((self.THUMB_SIZE + 60, self.THUMB_SIZE), Image.LANCZOS)
        x = self.CARD_PADDING

        tw, th = src.size
        # 圆角
        rounded = src.convert("RGBA")
        mask = _rounded_mask((tw, th), 10)
        rounded.putalpha(mask)

        # 放在带阴影的卡片上
        card_w = tw + 12
        card_h = th + 12
        card = Image.new("RGB", (card_w, card_h), (255, 255, 255))
        card_draw = ImageDraw.Draw(card)
        # 简单阴影
        card_draw.rounded_rectangle([(2, 2), (card_w - 1, card_h - 1)], radius=10, fill=(230, 230, 230))
        card.paste(rounded, (6, 6), rounded)

        canvas.paste(card, (x, y))

        draw = ImageDraw.Draw(canvas)
        label_x = x + card_w + 12
        draw.text((label_x, y + 6), "待搜索图片", font=self.body, fill=(100, 100, 100))

        return y + card_h + 4

    def _draw_result_card(
        self,
        draw: ImageDraw.Draw,
        canvas: Image.Image,
        index: int,
        item: dict,
        y: int,
    ) -> int:
        """绘制单条结果卡片（含缩略图预览）"""
        card_x = self.CARD_PADDING
        card_w = self.CARD_WIDTH - self.CARD_PADDING * 2
        card_h = self._row_height(item)
        radius = self.CARD_RADIUS

        # 卡片背景
        card_bg = (255, 255, 255)
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)],
            radius=radius,
            fill=card_bg,
        )
        # 细边框
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)],
            radius=radius,
            outline=(220, 220, 225),
            width=1,
        )

        inner_x = card_x + self.CARD_PADDING
        inner_y = y + self.ROW_PADDING_V

        # ── 缩略图 ──
        thumb = item.get('thumbnail_image')
        if thumb and isinstance(thumb, Image.Image):
            th = thumb.copy()
            th.thumbnail((self.THUMB_SIZE, self.THUMB_SIZE), Image.LANCZOS)
            tw, th_h = th.size
            th_rounded = th.convert("RGBA")
            th_mask = _rounded_mask((tw, th_h), 8)
            th_rounded.putalpha(th_mask)

            # 缩略图放在卡片内居中
            th_y = inner_y + (card_h - self.ROW_PADDING_V * 2 - th_h) // 2
            canvas.paste(th_rounded, (inner_x, th_y), th_rounded)
            text_x = inner_x + tw + self.THUMB_GAP
        else:
            # 无缩略图时用占位
            text_x = inner_x

        # ── 文字信息 ──
        text_y = inner_y

        # 序号 + 来源
        source = item.get('source', '未知来源')
        draw.text((text_x, text_y), f"{source}", font=self.body, fill=(30, 30, 30))
        text_y += 22

        # 标题
        title_text = item.get('title', '')
        if title_text:
            # 截断过长标题
            if len(title_text) > 60:
                title_text = title_text[:57] + '...'
            draw.text((text_x, text_y), title_text, font=self.small, fill=(90, 90, 90))
            text_y += 18

        # 画师
        author = item.get('author', '')
        if author:
            draw.text((text_x, text_y), f"作者: {author}", font=self.small, fill=(120, 120, 120))
            text_y += 18

        # 相似度条
        sim_str = item.get('similarity', '')
        if sim_str:
            try:
                similarity = float(sim_str.replace('%', '').replace('\uff05', ''))
            except (ValueError, TypeError):
                similarity = 0
            if similarity > 0:
                _draw_similarity_bar(draw, text_x, text_y, 140, similarity, self.small, (80, 80, 80))
                text_y += 24

        # 链接
        url = item.get('url', '')
        if url:
            short_url = url[:60] + '...' if len(url) > 60 else url
            draw.text((text_x, text_y), short_url, font=self.mono, fill=(41, 98, 255))
            text_y += 16

        return y + card_h

    def render_error(self, engine: str, error_msg: str) -> Image.Image:
        """绘制错误提示图"""
        w, h = self.CARD_WIDTH, 200
        canvas = Image.new("RGB", (w, h), (248, 249, 250))
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
            (self.CARD_PADDING, 16),
            f"「{label}」搜索失败",
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
