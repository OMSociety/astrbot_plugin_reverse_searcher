"""引擎介绍表格的 PIL 兜底绘制。

云端 t2i（HTML 模板渲染）不可达/超时时的本地降级路径，
从 main.py 抽出：入参 only（available_engines + 触发关键词回调），
引擎 URL/二次元标记自 ENGINE_REGISTRY 派生，返回 JPEG bytes。
"""

from __future__ import annotations

import io
from pathlib import Path
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageFont

from .engine_registry import COLOR_THEME, ENGINE_REGISTRY

# 渲染用引擎信息视图（从 ENGINE_REGISTRY 派生，仅本模块使用）
_ENGINE_INFO = {
    name: {"url": def_.url, "anime": def_.anime_focused}
    for name, def_ in ENGINE_REGISTRY.items()
}

_FONT_PATH = Path(__file__).parent / "resource/font/NotoSansSC-Regular.otf"


def create_engine_intro_image(
    available_engines: list[str], keyword_for: Callable[[str], str]
) -> bytes:
    """绘制引擎表格图，返回 JPEG bytes。

    Args:
        available_engines: 启用的引擎名列表（按显示顺序）
        keyword_for: 引擎名 -> 触发关键词（未配置关键词时返回引擎名本身）
    """
    width = 1000
    cell_height = 50
    header_height = 60
    title_height = 70
    table_height = header_height + cell_height * len(available_engines)
    height = title_height + table_height + 25
    border_width = 2

    def rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=1):
        x1, y1, x2, y2 = xy
        diameter = 2 * radius
        draw.rectangle(
            [x1 + radius, y1, x2 - radius, y2],
            fill=fill,
            outline=outline,
            width=width,
        )
        draw.rectangle(
            [x1, y1 + radius, x2, y2 - radius],
            fill=fill,
            outline=outline,
            width=width,
        )
        draw.pieslice(
            [x1, y1, x1 + diameter, y1 + diameter],
            180,
            270,
            fill=fill,
            outline=outline,
            width=width,
        )
        draw.pieslice(
            [x2 - diameter, y1, x2, y1 + diameter],
            270,
            360,
            fill=fill,
            outline=outline,
            width=width,
        )
        draw.pieslice(
            [x1, y2 - diameter, x1 + diameter, y2],
            90,
            180,
            fill=fill,
            outline=outline,
            width=width,
        )
        draw.pieslice(
            [x2 - diameter, y2 - diameter, x2, y2],
            0,
            90,
            fill=fill,
            outline=outline,
            width=width,
        )

    img = Image.new("RGB", (width, height), COLOR_THEME["bg"])
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype(str(_FONT_PATH), 24)
        header_font = ImageFont.truetype(str(_FONT_PATH), 18)
        body_font = ImageFont.truetype(str(_FONT_PATH), 16)
    except Exception:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    rounded_rectangle(
        draw,
        [20, 15, width - 20, title_height - 5],
        10,
        fill=COLOR_THEME["header_bg"],
    )
    title = "可用搜索引擎"
    title_width = (
        draw.textlength(title, font=title_font)
        if hasattr(draw, "textlength")
        else title_font.getsize(title)[0]
    )
    title_x = (width - title_width) // 2
    draw.text((title_x, 25), title, font=title_font, fill=COLOR_THEME["header_text"])
    table_x = 20
    table_width = width - 40
    col_widths = [
        int(table_width * 0.15),
        int(table_width * 0.40),
        int(table_width * 0.20),
        int(table_width * 0.25),
    ]
    table_y = title_height + 10
    table_bottom = table_y + header_height + cell_height * len(available_engines)
    draw.rectangle(
        [table_x, table_y, table_x + sum(col_widths), table_y + header_height],
        fill=COLOR_THEME["table_header"],
    )
    y = table_y + header_height
    for idx in range(len(available_engines)):
        row_bg = (
            COLOR_THEME["cell_bg_even"] if idx % 2 == 0 else COLOR_THEME["cell_bg_odd"]
        )
        draw.rectangle(
            [table_x, y, table_x + sum(col_widths), y + cell_height],
            fill=row_bg,
        )
        y += cell_height
    headers = ["引擎", "网址", "二次元图片专用", "关键词"]
    x = table_x
    for i, header in enumerate(headers):
        text_width = (
            draw.textlength(header, font=header_font)
            if hasattr(draw, "textlength")
            else header_font.getsize(header)[0]
        )
        text_x = x + (col_widths[i] - text_width) // 2
        draw.text(
            (text_x, table_y + (header_height - 18) // 2),
            header,
            font=header_font,
            fill=COLOR_THEME["text"],
        )
        x += col_widths[i]
    y = table_y + header_height
    for idx, engine in enumerate(available_engines):
        info = _ENGINE_INFO[engine]
        x = table_x
        draw.text(
            (x + 15, y + (cell_height - 16) // 2),
            engine,
            font=body_font,
            fill=COLOR_THEME["text"],
        )
        x += col_widths[0]
        draw.text(
            (x + 15, y + (cell_height - 16) // 2),
            info["url"],
            font=body_font,
            fill=COLOR_THEME["url"],
        )
        x += col_widths[1]
        mark = "✓" if info["anime"] else "×"
        mark_color = COLOR_THEME["success"] if info["anime"] else COLOR_THEME["fail"]
        mark_width = (
            draw.textlength(mark, font=header_font)
            if hasattr(draw, "textlength")
            else header_font.getsize(mark)[0]
        )
        draw.text(
            (x + (col_widths[2] - mark_width) // 2, y + (cell_height - 18) // 2),
            mark,
            font=header_font,
            fill=mark_color,
        )
        x += col_widths[2]
        keyword = keyword_for(engine)
        draw.text(
            (x + 15, y + (cell_height - 16) // 2),
            keyword,
            font=body_font,
            fill=COLOR_THEME["hint"],
        )
        y += cell_height
    draw.rectangle(
        [table_x, table_y, table_x + sum(col_widths), table_bottom],
        outline=COLOR_THEME["border"],
        width=border_width,
    )
    for i in range(1, len(available_engines) + 1):
        line_y = table_y + header_height + cell_height * i
        if i < len(available_engines):
            draw.line(
                [(table_x, line_y), (table_x + sum(col_widths), line_y)],
                fill=COLOR_THEME["border"],
                width=border_width,
            )
    draw.line(
        [
            (table_x, table_y + header_height),
            (table_x + sum(col_widths), table_y + header_height),
        ],
        fill=COLOR_THEME["border"],
        width=border_width,
    )
    col_x = table_x
    for i in range(len(col_widths) - 1):
        col_x += col_widths[i]
        draw.line(
            [(col_x, table_y), (col_x, table_bottom)],
            fill=COLOR_THEME["border"],
            width=border_width,
        )
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    output.seek(0)
    return output.getvalue()
