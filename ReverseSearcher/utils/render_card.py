"""搜索结果卡片渲染器

纯 PIL 手绘结果卡片，无外部依赖。
支持引擎色顶栏、卡片阴影、左侧装饰条、编号徽章、缩略图宽高比保持、相似度进度条、圆角卡片。
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from ..engine_registry import ENGINE_REGISTRY

# ── 字体 ────────────────────────────────────────────────


_font_cache = None


def _load_fonts() -> tuple:
    """加载插件内置中文字体（模块级懒加载单例）"""
    global _font_cache
    if _font_cache is not None:
        return _font_cache
    try:
        from pathlib import Path

        base_dir = Path(__file__).parent.parent
        regular_font = str(base_dir / "resource/font/NotoSansSC-Regular.otf")
        heavy_font = str(base_dir / "resource/font/SourceHanSansSC-Heavy.otf")

        small = ImageFont.truetype(regular_font, 16)
        body = ImageFont.truetype(regular_font, 18)
        title = ImageFont.truetype(heavy_font, 26)
        header_font = ImageFont.truetype(regular_font, 20)
        mono = ImageFont.truetype(regular_font, 14)
        _font_cache = (small, body, title, header_font, mono)
        return _font_cache
    except Exception:
        d = ImageFont.load_default()
        _font_cache = (d, d, d, d, d)
        return _font_cache


# ── 辅助函数 ────────────────────────────────────────────


def _hex_to_rgb(hex_str: str) -> tuple:
    h = hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rounded_mask(size: tuple, radius: int) -> Image.Image:
    """生成圆角矩形 alpha mask"""
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
    return mask


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
        draw.rounded_rectangle(
            [x, y, x + fill_w, y + bar_h], radius=radius, fill=bar_color
        )

    text = f"{similarity:.1f}%"
    if hasattr(font, "getbbox"):
        font.getbbox(text)[2]
    else:
        font.getsize(text)[0]
    draw.text((x + width + 8, y - 7), text, font=font, fill=text_color)


# ── 主渲染器 ────────────────────────────────────────────


class ResultCardRenderer:
    """手绘搜索结果卡片"""

    CARD_WIDTH = 960
    CARD_PADDING = 24
    THUMB_SIZE = 160  # 缩略图最大边长
    THUMB_GAP = 24
    HEADER_H = 72
    SOURCE_H = 180
    CARD_RADIUS = 12
    ROW_PADDING_V = 20
    ACCENT_W = 5  # 左侧装饰条宽度
    BADGE_R = 12  # 编号徽章半径（当前未启用）

    def __init__(self):
        self.small, self.body, self.title, self.header_font, self.mono = _load_fonts()

    # ── 渲染入口 ──────────────────────────────────────────

    def render(
        self,
        engine: str,
        results: list[dict],
        source_image: Image.Image | None = None,
        ai_detect: bool | None = None,
    ) -> Image.Image:
        """渲染结果卡片"""
        engine_color = self._get_engine_color(engine)
        total_height = self._calc_height(results, source_image, ai_detect)
        bg_color = (248, 249, 250)
        canvas = Image.new("RGB", (self.CARD_WIDTH, total_height), bg_color)
        draw = ImageDraw.Draw(canvas)

        self._draw_header(draw, engine, engine_color, len(results))

        y = self.CARD_PADDING + self.HEADER_H
        if ai_detect is not None:
            y = self._draw_ai_badge(draw, canvas, ai_detect, y)
        if source_image:
            y = self._draw_source_thumb(canvas, source_image, y)

        y += self.ROW_PADDING_V
        for i, item in enumerate(results[:5]):
            y = self._draw_result_card(draw, canvas, i + 1, item, y, engine_color)
            y += self.ROW_PADDING_V

        return canvas

    # ── 尺寸计算 ──────────────────────────────────────────

    def _get_engine_color(self, engine: str) -> tuple:
        """获取引擎主题色 RGB"""
        engine_def = ENGINE_REGISTRY.get(engine, None)
        if engine_def:
            return _hex_to_rgb(
                f"#{engine_def.color[0]:02x}{engine_def.color[1]:02x}{engine_def.color[2]:02x}"
            )
        return (74, 110, 169)

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
            h += self.SOURCE_H + 12  # source gap
        h += self.CARD_PADDING
        for item in results[:5]:
            h += self._row_height(item)
        h += self.ROW_PADDING_V * (min(len(results), 5) + 2)
        h += self.CARD_PADDING
        return h

    def _row_height(self, item: dict) -> int:
        """计算单行卡片高度，适配可变缩略图尺寸"""
        thumb = item.get("thumbnail_image")
        if thumb and isinstance(thumb, Image.Image):
            ow, oh = thumb.size
            if ow > oh:
                thumb_h = max(int(oh * self.THUMB_SIZE / ow), 60)
            else:
                thumb_h = self.THUMB_SIZE
        else:
            thumb_h = 0

        # 文字行数
        text_lines = 1  # source
        if item.get("title"):
            text_lines += 1
        if item.get("author"):
            text_lines += 1
        if item.get("similarity"):
            text_lines += 1
        text_h = text_lines * 26 + self.ROW_PADDING_V * 2

        return max(thumb_h + self.ROW_PADDING_V * 2, text_h, 72)

    # ── 顶栏 ──────────────────────────────────────────────

    def _draw_header(
        self,
        draw: ImageDraw.Draw,
        engine: str,
        color: tuple,
        count: int,
    ) -> None:
        """绘制引擎色纯色顶栏（无渐变）"""
        engine_def = ENGINE_REGISTRY.get(engine, None)
        draw.rectangle([(0, 0), (self.CARD_WIDTH, self.HEADER_H)], fill=color)

        label = engine_def.label if engine_def else engine.upper()
        text = f"「{label}」搜索结果 — {count} 条匹配"
        if hasattr(draw, "textlength"):
            tw = draw.textlength(text, font=self.title)
        else:
            tw = self.title.getsize(text)[0]
        draw.text(
            ((self.CARD_WIDTH - tw) // 2, 18),
            text,
            font=self.title,
            fill=(255, 255, 255),
        )

    # ── AI 标签 ───────────────────────────────────────────

    def _draw_ai_badge(
        self, draw: ImageDraw.Draw, canvas: Image.Image, ai: bool, y: int
    ) -> int:
        """绘制 AI 检测结果标签"""
        badge_w = 220
        badge_h = 34
        x = self.CARD_PADDING

        if ai:
            badge_color = (255, 138, 101)
            label = "⚠ AI 生成嫌疑"
        else:
            badge_color = (102, 187, 106)
            label = "✓ 非 AI 生成"

        draw.rounded_rectangle(
            [(x, y), (x + badge_w, y + badge_h)],
            radius=6,
            fill=badge_color,
        )
        if hasattr(draw, "textlength"):
            tw = draw.textlength(label, font=self.small)
        else:
            tw = self.small.getsize(label)[0]
        draw.text(
            (x + (badge_w - tw) // 2, y + 7),
            label,
            font=self.small,
            fill=(255, 255, 255),
        )
        return y + badge_h + 10

    # ── 源图缩略图 ───────────────────────────────────────

    def _draw_source_thumb(
        self, canvas: Image.Image, source: Image.Image, y: int
    ) -> int:
        """绘制源图缩略图"""
        src = source.copy()
        src.thumbnail((self.THUMB_SIZE + 80, self.THUMB_SIZE), Image.LANCZOS)
        x = self.CARD_PADDING

        tw, th = src.size
        rounded = src.convert("RGBA")
        mask = _rounded_mask((tw, th), 10)
        rounded.putalpha(mask)

        card_w = tw + 12
        card_h = th + 12
        card = Image.new("RGB", (card_w, card_h), (255, 255, 255))
        card_draw = ImageDraw.Draw(card)
        card_draw.rounded_rectangle(
            [(2, 2), (card_w - 1, card_h - 1)], radius=10, fill=(230, 230, 230)
        )
        card.paste(rounded, (6, 6), rounded)

        canvas.paste(card, (x, y))
        return y + card_h + 4

    # ── 结果卡片（核心）───────────────────────────────────

    def _draw_result_card(
        self,
        draw: ImageDraw.Draw,
        canvas: Image.Image,
        index: int,
        item: dict,
        y: int,
        engine_color: tuple,
    ) -> int:
        """绘制单条结果卡片

        包含：阴影、左侧装饰条、编号徽章、缩略图(保持宽高比)、文字信息、相似度条
        """
        card_x = self.CARD_PADDING
        card_w = self.CARD_WIDTH - self.CARD_PADDING * 2
        card_h = self._row_height(item)
        radius = self.CARD_RADIUS

        # ── 阴影 ──
        shadow_offset = 3
        draw.rounded_rectangle(
            [
                (card_x + shadow_offset, y + shadow_offset),
                (card_x + card_w + shadow_offset, y + card_h + shadow_offset),
            ],
            radius=radius,
            fill=(200, 200, 208),
        )

        # ── 白色卡片背景 ──
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)],
            radius=radius,
            fill=(255, 255, 255),
        )
        draw.rounded_rectangle(
            [(card_x, y), (card_x + card_w, y + card_h)],
            radius=radius,
            outline=(215, 215, 222),
            width=1,
        )

        # ── 左侧装饰条 ──
        draw.rectangle(
            [(card_x, y + radius), (card_x + self.ACCENT_W, y + card_h - radius)],
            fill=engine_color,
        )

        # ── 文字起始偏移 ──
        text_x = card_x + self.ACCENT_W + 16
        inner_y = y + self.ROW_PADDING_V

        # ── 缩略图（保持宽高比）──
        thumb = item.get("thumbnail_image")
        if thumb and isinstance(thumb, Image.Image):
            th = thumb.copy()
            ow, oh = th.size
            # 以 THUMB_SIZE 为最大边长，保持宽高比
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

        # ── 文字信息 ──
        text_y = inner_y + 6

        # 来源
        source = item.get("source", "未知来源")
        draw.text((text_x, text_y), source, font=self.body, fill=(30, 30, 30))
        text_y += 26

        # 标题
        title_text = item.get("title", "")
        if title_text:
            if len(title_text) > 36:
                title_text = title_text[:33] + "..."
            draw.text((text_x, text_y), title_text, font=self.small, fill=(90, 90, 90))
            text_y += 22

        # 画师
        author = item.get("author", "")
        if author:
            draw.text(
                (text_x, text_y),
                f"作者: {author}",
                font=self.small,
                fill=(120, 120, 120),
            )
            text_y += 22

        # 相似度条
        sim_str = item.get("similarity", "")
        if sim_str:
            try:
                similarity = float(sim_str.replace("%", "").replace("\uff05", ""))
            except (ValueError, TypeError):
                similarity = 0
            if similarity > 0:
                _draw_similarity_bar(
                    draw,
                    text_x,
                    text_y + 8,
                    200,
                    similarity,
                    self.small,
                    (80, 80, 80),
                )
                text_y += 26

        # 链接
        url = item.get("url", "")
        if url:
            short_url = url[:60] + "..." if len(url) > 60 else url
            draw.text((text_x, text_y), short_url, font=self.mono, fill=(41, 98, 255))

        return y + card_h

    # ── 错误渲染 ──────────────────────────────────────────

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
