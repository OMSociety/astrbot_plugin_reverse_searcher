"""测试夹具与辅助工具"""

import io

import pytest

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


# ── 示例 HTML / JSON ───────────────────────


@pytest.fixture
def mock_gemini_response():
    """模拟 Gemini 搜索 API 返回的原始结果列表"""
    return [
        {
            "i": "https://example.com/img1.jpg",
            "page_url": "https://example.com/page1",
            "title": "示例图片1",
            "domain": "example.com",
        },
        {
            "i": "https://example.com/img2.jpg",
            "page_url": "https://example.com/page2",
            "title": "示例图片2",
            "domain": "example.com",
        },
    ]


@pytest.fixture
def mock_google_lens_html():
    """模拟 Google Lens 页面 HTML"""
    return """
    <html><head><title>Google Lens</title></head><body>
    <div class="vWYmec"></div>
    <script>
    AF_initDataCallback({
        key: "ds:1",
        data: [
            [],
            [
                [
                    null,
                    null,
                    [
                        "https://example.com/thumb1.jpg",
                        "https://example.com/thumb1.jpg",
                    ],
                    "Title 1",
                ]
            ]
        ]
    });
    </script>
    </body></html>
    """
