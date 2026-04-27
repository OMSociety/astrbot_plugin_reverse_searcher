# 图片反搜助手

> 核心代码基于 [kitUIN/PicImageSearch](https://github.com/kitUIN/PicImageSearch)

支持 AnimeTrace、E-Hentai、Google Lens、Yandex、SauceNAO 的图片反向搜索。**搜索结果自动生成为精美卡片图片**（渐变顶栏、圆角缩略图、相似度进度条），无需依赖任何外部渲染库，纯 PIL 手绘。同时提供 LLM 主动搜图工具，让芙兰自己判断何时搜图、用哪个引擎。

---

## ✨ 插件特色：搜索结果卡片生成

搜索结果不是干巴巴的文字，而是自动渲染为一张精美卡片图片：

- 🎨 **引擎主题色渐变顶栏** — 不同引擎不同配色，一眼能认出是哪家搜的
- 🖼️ **源图 + 结果缩略图** — 待搜索图片和匹配结果同框展示
- 📊 **相似度彩色进度条** — 绿色（≥90%）/ 橙色（≥70%）/ 红色（<70%），直观
- 📝 **完整信息展示** — 来源、标题、画师、链接一个不落
- 🧩 **纯 PIL 手绘，零依赖** — 不装 matplotlib、不装 opencv，就只有 Pillow

---

## 功能列表

### 关键词触发
发送 `以图搜图`（或自定义关键词），然后附上图片：
```
以图搜图
[图片]
```

可选参数：
- 引擎别名：`a`=animetrace, `s`=saucenao, `e`=ehentai, `g`=google, `y`=yandex

### LLM 主动搜图
芙兰可以根据对话意图自主调用搜图工具，例如：
- "帮我看看这是哪个角色" → 自动用 animetrace
- "这张图找出处" → 自动用 saucenao

---

## 安装

### 方式一：插件市场
- **AstrBot WebUI** → **插件市场** → 搜索关键词或唯一标识符 `astrbot_plugin_reverse_searcher`

### 方式二：GitHub 仓库
- **AstrBot WebUI** → **插件管理** → **+ 安装**
- 粘贴仓库地址：`https://github.com/OMSociety/astrbot_plugin_reverse_searcher`

### 依赖安装
```bash
pip install -r requirements.txt
```
核心依赖：`httpx`, `Pillow`, `pyquery`, `typing_extensions`

---

## 支持的搜索引擎

| 引擎 | 说明 | 备注 |
|:----|:----|:----|
| **animetrace** | 动漫角色识别 | 无需 API Key，返回作品名+角色名 |
| **saucenao** | 综合出处搜索 | 免费 Key 够用，P Pixiv 插画首选 |
| **google** | Google Lens | 需 SerpAPI Key（推荐），综合搜索兜底 |
| **yandex** | 相似图片搜索 | 无需配置，俄罗斯引擎 |
| **ehentai** | E-Hentai/ExHentai | 仅 ExHentai 需要 Cookie |

---

## 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `enable_keyword_trigger` | bool | `true` | 关闭后不再响应关键词，但 LLM 工具仍可用 |
| `serpapi_key` | string | - | SerpAPI Key，从 [serpapi.com](https://serpapi.com/) 申请 |
| `zenserp_key` | string | - | 备用 SerpAPI，从 [zenserp.com](https://zenserp.com/) 申请 |
| `api_key` | string | - | SauceNAO API Key，从 [saucenao.com](https://saucenao.com/user.php) 申请 |
| `cookies` | string | - | 仅使用 ExHentai 时需要 |
| `proxies` | string | - | 代理服务器地址 |
| `auto_send_text_results` | bool | `false` | 搜索完成后自动发送文本结果 |
| `timeout_settings` | object | - | 超时配置（见下方详情） |

### 超时配置 `timeout_settings`

| 子配置 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `search_params_timeout` | int | `30` | 等待搜索参数的最大时间（秒） |
| `text_confirm_timeout` | int | `30` | 等待确认结果格式的最大时间（秒） |

### AnimeTrace 参数

| 子配置 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `model` | string | `full_game_model_kira` | 识别模型 |
| `is_multi` | bool | `false` | 多角色搜索模式 |
| `ai_detect` | bool | `false` | AI 检测模式 |

---

## LLM 可调用工具

### reverse_search
通用搜图工具，自动判断引擎。

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_base64` | string | 图片 base64 编码（可选） |
| `image_url` | string | 图片 URL（可选，与 base64 二选一） |
| `engine` | string | 指定引擎（可选，不填则自动判断） |
| `intent` | string | 搜索意图（如"找角色"、"找出处"），用于自动选引擎 |

### reverse_search_with_engine
指定引擎搜图。

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_base64` / `image_url` | string | 图片来源 |
| `engine` | string | **必填**，引擎名称 |

---

## 致谢

- 核心代码：[kitUIN/PicImageSearch](https://github.com/kitUIN/PicImageSearch)