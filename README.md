# 图片反搜助手

支持 AnimeTrace、E-Hentai、Google Lens、Yandex、SauceNAO 的图片反向搜索，同时提供 LLM 主动搜图工具，让芙兰自己判断何时搜图、用哪个引擎。

> ⚡ 核心代码基于 [kitUIN/PicImageSearch](https://github.com/kitUIN/PicImageSearch)

---

## 安装方法

### 方式一：插件市场

- 打开 **AstrBot WebUI** → **插件市场** → 搜索关键词
- 或直接用唯一标识符搜索：
  ```
  astrbot_plugin_reverse_searcher
  ```

### 方式二：GitHub 仓库链接

- 打开 **AstrBot WebUI** → **插件管理** → **+ 安装**
- 粘贴仓库地址：
  ```
  https://github.com/OMSociety/astrbot_plugin_reverse_searcher
  ```

### 依赖安装

```bash
pip install -r requirements.txt
```

核心依赖：`httpx`, `Pillow`, `pyquery`, `typing_extensions`

---

## 使用方法

### 方式一：关键词触发

发送 `以图搜图`（或自定义关键词），然后附上图片：

```
以图搜图
[图片]
```

可选参数：
- 引擎别名：`a`=animetrace, `s`=saucenao, `e`=ehentai, `g`=google, `y`=yandex

示例：
```
以图搜图 a
[图片]
```

### 方式二：LLM 工具（芙兰主动搜图）

芙兰可以根据对话意图自主调用搜图工具，例如：

- "帮我看看这是哪个角色" → 自动用 animetrace
- "这张图找出处" → 自动用 saucenao
- "搜一下这张图" → 自动判断引擎

芙兰会在图片中有角色特征（角、翅膀、服装风格等）时优先用 animetrace，在搜索失败时自动重试。

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

### 默认参数

#### Google（SerpAPI）
- `serpapi_key`: 从 [serpapi.com](https://serpapi.com/) 申请
- `zenserp_key`: 备用，从 [zenserp.com](https://zenserp.com/) 申请

#### SauceNAO
- `api_key`: 从 [saucenao.com](https://saucenao.com/user.php) 申请

#### E-Hentai
- `cookies`: 仅使用 ExHentai 时需要

### 其他配置

| 配置项 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `enable_keyword_trigger` | bool | `true` | 关闭后不再响应关键词，但 LLM 工具仍可用 |
| `proxies` | string | - | 代理服务器地址 |
| `auto_send_text_results` | bool | `false` | 搜索完成后自动发送文本结果 |

---

## LLM 工具详细说明

### reverse_search

通用搜图工具，自动判断引擎。

**参数**：
- `image_base64`: 图片 base64 编码（可选，可从对话自动获取）
- `image_url`: 图片 URL（可选，与 base64 二选一）
- `engine`: 指定引擎（可选，不填则自动判断）
- `intent`: 搜索意图（如"找角色"、"找出处"），用于自动选引擎

### reverse_search_with_engine

指定引擎搜图。

**参数**：
- `image_base64` / `image_url`: 图片来源
- `engine`: **必填**，引擎名称

---

## 致谢

- 核心代码：[kitUIN/PicImageSearch](https://github.com/kitUIN/PicImageSearch)
