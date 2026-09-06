"""测试夹具与辅助工具"""

import io
import os
import sys

import pytest

# 让测试能 import 到顶层包 ReverseSearcher（插件根目录须在 sys.path 上）。
# pytest 默认只把 tests/ 目录加入 sys.path，无法解析到上一级的 ReverseSearcher 包。
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

# ── 示例图片 ──────────────────────────────


@pytest.fixture
def sample_image_bytes():
    """生成 1x1 的 PNG 图片（最小合法图片）"""
    import struct
    import zlib

    # 构建最小合法 PNG
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\xff"
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def sample_image_buffer(sample_image_bytes):
    """示例图片 io.BytesIO"""
    return io.BytesIO(sample_image_bytes)
