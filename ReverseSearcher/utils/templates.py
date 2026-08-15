"""搜索结果 HTML/Jinja2 卡片模板。

用于 AstrBot 文转图（html_renderer.render_custom_template）：
把反向搜索结果渲染成卡片图片（引擎色渐变 Header + 白色圆角卡片流）。

设计风格参考 astrbot.app 官网（天蓝 #3c96ca 主色 + 藏青渐变 + 圆角卡片 + 柔和阴影）。

注意：
- 源图/结果缩略图由调用方先转成 base64 data URI 内嵌（云端文转图服务
  无法访问本地文件与部分外链），渲染不依赖外网
- 字体用 CSS 字体栈，云端 t2i 渲染自动选择中文字体
"""

# 引擎介绍表格模板（main.py 的 _send_engine_intro 使用）
ENGINE_INTRO_TMPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  body {
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f2f4f8;
    margin: 0;
    padding: 18px;
    width: 720px;
  }
  .header {
    background: linear-gradient(135deg, #3c96ca 0%, #2b3f67 100%);
    border-radius: 12px;
    padding: 18px 22px;
    color: #fff;
    margin-bottom: 14px;
  }
  .header h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
  }
  .header p { margin: 4px 0 0; font-size: 13px; opacity: .85; }
  table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(17, 24, 39, .06);
  }
  th, td { padding: 12px 14px; text-align: left; font-size: 14px; }
  th {
    background: #eef4f8;
    color: #2b3f67;
    font-weight: 600;
  }
  td { border-top: 1px solid #f0f2f5; color: #374151; }
  tr:nth-child(even) td { background: #fafbfc; }
  .yes { color: #16a34a; font-weight: 600; }
  .no { color: #9ca3af; }
  .kw { color: #3c96ca; }
  .url { color: #6b7280; font-size: 13px; word-break: break-all; }
</style>
</head>
<body>
  <div class="header">
    <h1>🔍 可用搜索引擎</h1>
    <p>回复引擎名或关键词即可选择</p>
  </div>
  <table>
    <tr><th>引擎</th><th>网址</th><th>二次元专用</th><th>关键词</th></tr>
    {% for e in engines %}
    <tr>
      <td><b>{{ e.label }}</b></td>
      <td class="url">{{ e.url }}</td>
      <td>{% if e.anime %}<span class="yes">✓</span>{% else %}<span class="no">×</span>{% endif %}</td>
      <td class="kw">{{ e.keyword }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""

# 搜索结果卡片模板
RESULT_CARD_TMPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  body {
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f2f4f8;
    margin: 0;
    padding: 18px;
    width: 760px;
  }
  /* 引擎色渐变 Header */
  .header {
    background: linear-gradient(135deg, {{ engine_color }} 0%, #2b3f67 100%);
    border-radius: 14px;
    padding: 20px 24px;
    color: #fff;
    margin-bottom: 16px;
    box-shadow: 0 4px 14px rgba(43, 63, 103, .25);
  }
  .header-title { font-size: 22px; font-weight: 800; }
  .header-sub { font-size: 13px; opacity: .88; margin-top: 4px; }

  /* AI 检测徽章 */
  .ai-badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 12px;
  }
  .ai-badge.warn { background: #f59e0b; }
  .ai-badge.ok { background: #22c55e; }

  /* 源图区 */
  .source-row {
    display: flex;
    align-items: center;
    background: #fff;
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(17, 24, 39, .06);
  }
  .source-img {
    width: 84px;
    height: 84px;
    object-fit: cover;
    border-radius: 8px;
    background: #eef2f7;
  }
  .source-label { margin-left: 14px; font-size: 13px; color: #6b7280; }
  .source-label b { display: block; font-size: 15px; color: #1f2937; margin-top: 2px; }

  /* 结果卡片 */
  .card {
    display: flex;
    background: #ffffff;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(17, 24, 39, .06);
  }
  .thumb {
    width: 96px;
    height: 128px;
    object-fit: cover;
    border-radius: 8px;
    background: #eef2f7;
    flex-shrink: 0;
  }
  .thumb.flat { height: 96px; }
  .info { margin-left: 14px; flex: 1; min-width: 0; }
  .source {
    font-size: 15px;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .title {
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 6px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    word-break: break-all;
  }
  .author { font-size: 13px; color: #9ca3af; margin-bottom: 8px; }
  .badges { white-space: nowrap; }
  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    margin-right: 6px;
  }
  .sim-high { background: #dcfce7; color: #16a34a; }
  .sim-mid { background: #ffedd5; color: #ea580c; }
  .sim-low { background: #fee2e2; color: #dc2626; }
  .sim-none { background: #f3f4f6; color: #6b7280; }
  /* 结果链接：图片内按钮不可点击，直接展示可复制链接文本 */
  .link-row {
    font-size: 12px;
    color: #0284c7;
    margin-top: 6px;
    word-break: break-all;
    line-height: 1.4;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="header-title">「{{ engine_label }}」搜索结果</div>
    <div class="header-sub">{{ count }} 条匹配 · 图片反向搜索</div>
  </div>

  {% if ai_detect is not none %}
  <div class="ai-badge {{ 'warn' if ai_detect else 'ok' }}">{{ '⚠ AI 生成嫌疑' if ai_detect else '✓ 非 AI 生成' }}</div>
  {% endif %}

  {% if source_image_b64 %}
  <div class="source-row">
    <img class="source-img" src="{{ source_image_b64 }}">
    <div class="source-label">源图<b>待搜索图片</b></div>
  </div>
  {% endif %}

  {% for r in results %}
  <div class="card">
    {% if r.thumbnail_b64 %}
    <img class="thumb{{ ' flat' if r.thumb_flat else '' }}" src="{{ r.thumbnail_b64 }}">
    {% else %}
    <div class="thumb" style="display:flex;align-items:center;justify-content:center;color:#cbd5e1;font-size:28px;">🖼</div>
    {% endif %}
    <div class="info">
      <div class="source">{{ r.source }}</div>
      {% if r.title %}<div class="title">{{ r.title }}</div>{% endif %}
      {% if r.author %}<div class="author">👤 {{ r.author }}</div>{% endif %}
      <div class="badges">
        {% if r.similarity %}
        <span class="badge {{ r.sim_class }}">📊 {{ r.similarity }}</span>
        {% endif %}
      </div>
      {% if r.url %}
      <div class="link-row">🔗 {{ r.url }}</div>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</body>
</html>
"""

# 错误提示卡片模板
ERROR_TMPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  body {
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f2f4f8;
    margin: 0;
    padding: 18px;
    width: 560px;
  }
  .card {
    background: linear-gradient(135deg, {{ engine_color }} 0%, #2b3f67 100%);
    border-radius: 14px;
    padding: 24px 26px;
    color: #fff;
    box-shadow: 0 4px 14px rgba(43, 63, 103, .25);
  }
  .title { font-size: 20px; font-weight: 800; }
  .msg { margin-top: 10px; font-size: 14px; opacity: .9; word-break: break-all; }
</style>
</head>
<body>
  <div class="card">
    <div class="title">「{{ engine_label }}」搜索失败</div>
    <div class="msg">{{ error_msg }}</div>
  </div>
</body>
</html>
"""
