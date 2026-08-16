<div align="center">

<img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_reverse_searcher/main/logo.png" width="120" alt="ReverseSearcher Logo" />

# 🔍 图片反搜助手

**五大引擎反向搜图** —— AnimeTrace 认角色 · SauceNAO 找出处 · Google Lens 兜底 · Yandex 找相似 · E-Hentai 搜本子

[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/OMSociety/astrbot_plugin_reverse_searcher)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/stargazers)
[![Issues](https://img.shields.io/github/issues/OMSociety/astrbot_plugin_reverse_searcher)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues)

[✨ 核心特性](#-核心特性) • [📖 功能概览](#-功能概览) • [🚀 快速开始](#-快速开始) • [🔍 支持的搜索引擎](#-支持的搜索引擎) • [⚙️ 配置项说明](#️-配置项说明) • [🛠️ LLM 可调用工具](#️-llm-可调用工具) • [🔧 常见问题](#-常见问题) • [📝 更新日志](CHANGELOG.md)

</div>

> 🎨 本项目由 AI 编写，部分源码基于 [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2)

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🔍 **五大搜索引擎** | AnimeTrace 认角色、SauceNAO 找出处、Google Lens 综合兜底、Yandex 找相似、E-Hentai 搜本子，各司其职 |
| 💬 **关键词触发** | 发送 `以图搜图` + 图片即可搜索，支持引擎别名快捷指定（`a`/`s`/`e`/`g`/`y`） |
| 🤖 **LLM 主动搜图** | 机器人根据对话意图自主判断何时搜图、用哪个引擎，无需手动指令 |
| 🧭 **意图路由** | 基于关键词加权匹配自动选择最优引擎——说「这是谁」自动走 AnimeTrace |
| 🎴 **精美结果卡片** | 搜索结果渲染为现代卡片图片（引擎色渐变 Header、相似度彩色徽章、AI 检测标签），云端文转图不可达时自动降级 PIL |
| 🔄 **多引擎自由切换** | 引擎按需启停，失败可自动切换候补引擎 |

---

## 📖 功能概览

### 搜索卡片渲染
搜索完成后自动生成一张卡片图片：源图 + 结果缩略图同框，相似度一目了然：

<img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_reverse_searcher/main/docs/search_example.png" alt="搜索结果卡片示例" width="480" />

### 关键词触发
发送 `以图搜图` 并附上图片（或回复引用消息），即可按引导完成搜索：

```
用户: 以图搜图
🤖 → 发送引擎介绍卡片，请选择引擎
用户: a 这张图
🤖 → 已选择 AnimeTrace，正在搜索...
     → 发送搜索结果卡片 ✅
```

### LLM 主动搜图
机器人内置 `reverse_search` 工具，根据对话内容自主判断是否搜图：

```
用户: 芙兰，帮我看看这张图的角色是谁
🤖 → reverse_search(intent=找角色)
    🔍 [AnimeTrace] 找到 3 个结果
    角色: 芙兰朵露·斯卡蕾特 | 作品: 东方Project...
```

### 意图路由
无需指定引擎，说意图即可自动选：

| 意图 | 自动路由 |
|------|---------|
| 「这是谁 / 哪个角色 / cos」 | → AnimeTrace |
| 「找出处 / 找作者 / pixiv pid」 | → SauceNAO |
| 「找相似图 / 像这个」 | → Yandex |
| 「找本子 / 同人」 | → E-Hentai |
| 「找原图 / 综合搜索」 | → Google |

---

## 🚀 快速开始

### 第一步：安装

**方式一：插件市场**
- AstrBot WebUI → 插件市场 → 搜索 `astrbot_plugin_reverse_searcher`

**方式二：GitHub 仓库**
- AstrBot WebUI → 插件管理 → ＋ 安装 → 粘贴仓库地址：
- `https://github.com/OMSociety/astrbot_plugin_reverse_searcher`

### 第二步：最小配置（装好即用）

**无需任何配置**即可使用 AnimeTrace、Yandex、E-Hentai 三个免 Key 引擎：

1. 重启 AstrBot 后，直接发送 `以图搜图` + 图片
2. 或直接对机器人说「帮我看看这个角色是谁」让 LLM 自动搜图

> 💡 可选增强：配置 SauceNAO `api_key`（[申请地址](https://saucenao.com/user.php)）解锁画师/出处搜索；Google 引擎需 [SerpAPI Key](https://serpapi.com/)；ExHentai 需有效 Cookie。

### 依赖安装
插件依赖 `httpx`、`Pillow`、`pyquery` 等，AstrBot 安装插件时自动处理。

---

## 🔍 支持的搜索引擎

| 引擎 | 说明 | 需要配置 |
|:----|:----|:----|
| **animetrace** | 动漫角色识别（最强），返回作品名 + 角色名 | ❌ 免配置 |
| **yandex** | 相似图片搜索 | ⚠️ 建议配 Cookie（Yandex 反爬严格，未配置时可能 CAPTCHA/无结果） |
| **ehentai** | E-Hentai 同人本搜索 | ❌ 免配置（ExHentai 需 Cookie） |
| **saucenao** | 综合出处搜索，Pixiv 插画首选 | ⚠️ 建议配 `api_key` |
| **google** | Google Lens 综合兜底 | ✅ 需 SerpAPI Key |

---

## ⚙️ 配置项说明

### 顶层配置

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `enable_keyword_trigger` | bool | `true` | 关键词触发开关；关闭后仅 LLM 工具可用 |
| `proxies` | string | `""` | 代理地址，如 `http://127.0.0.1:7890`（国内访问必填） |

### 超时配置 `timeout_settings`

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `search_params_timeout` | int | `30` | 等待用户补充引擎/图片的超时（秒） |

### 关键词 `keyword`

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `trigger_keywords` | list | `["以图搜图"]` | 触发搜索的关键词列表 |
| `engine_keywords` | object | `a/s/e/g/y` | 各引擎的自定义别名（animetrace=`a`、saucenao=`s`、ehentai=`e`、google=`g`、yandex=`y`） |

### 引擎启用 `available_apis`

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `animetrace` / `ehentai` / `google` / `yandex` / `saucenao` | bool | `true` | 各引擎启停开关 |

### 引擎默认参数 `default_params`

| 配置项 | 说明 |
|--------|------|
| `animetrace.model` | 识别模型，默认 `full_game_model_kira` |
| `animetrace.is_multi` / `ai_detect` | 多角色搜索 / AI 检测开关 |
| `ehentai.is_ex` / `covers` / `similar` / `exp` | ExHentai 开关、封面/相似/实验模式 |
| `ehentai.cookies` | **E-Hentai Cookie**（ExHentai 必需，获取方法见常见问题 Q5） |
| `google.serpapi_key` / `zenserp_key` | SerpAPI（推荐）/ Zenserp（备用）Key |
| `google.hl` / `country` / `max_results` | 语言 / 地区 / 最大结果数 |
| `saucenao.api_key` / `minsim` / `numres` | API Key / 最低相似度 / 结果数 |
| `yandex.max_results` / `use_ru_fallback` | 结果数 / `.ru` 域名回退 |
| `yandex.cookies` | **Yandex Cookie**（反爬严格，不填可能 CAPTCHA 无结果，获取方法见 Q5） |

### 快速配置模板

```json
{
  "enable_keyword_trigger": true,
  "proxies": "",
  "timeout_settings": {
    "search_params_timeout": 30
  },
  "keyword": {
    "trigger_keywords": ["以图搜图"],
    "engine_keywords": { "animetrace": "a", "ehentai": "e", "google": "g", "yandex": "y", "saucenao": "s" }
  },
  "available_apis": { "animetrace": true, "ehentai": true, "google": true, "yandex": true, "saucenao": true },
  "default_params": {
    "animetrace": { "model": "full_game_model_kira", "is_multi": false, "ai_detect": false },
    "ehentai": { "is_ex": false, "covers": false, "similar": true, "exp": false, "cookies": "" },
    "google": { "serpapi_key": "", "zenserp_key": "", "hl": "zh-CN", "country": "HK", "max_results": 10 },
    "saucenao": { "api_key": "", "hide": 3, "numres": 5, "minsim": 30, "output_type": 2 },
    "yandex": { "max_results": 10, "use_ru_fallback": true, "cookies": "" }
  }
}
```

---

## 🛠️ LLM 可调用工具

插件注册 2 个 LLM 工具，机器人会自主判断何时调用：

```
用户: 这张图是什么角色？
🤖 → reverse_search(intent=找角色)
    🔍 [AnimeTrace] 找到 3 个结果
    角色: 芙兰朵露·斯卡蕾特 | 作品: 东方Project...

用户: 用 SauceNAO 查一下这张图的画师
🤖 → reverse_search_with_engine(engine=saucenao)
    🔍 [SauceNAO] 找到 5 个结果
    Pixiv: 画师 KuroNeko | 相似度 95.2%
```

### reverse_search
通用搜图工具，根据意图自动选择引擎。

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_base64` | string? | 图片 base64 编码（与 URL 二选一） |
| `image_url` | string? | 图片 URL（与 base64 二选一） |
| `intent` | string? | 搜索意图（如「找角色」「找出处」「找相似图」），用于自动选引擎 |

### reverse_search_with_engine
指定引擎搜图，当用户明确要求使用某引擎时调用。

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_base64` / `image_url` | string? | 图片来源（二选一） |
| `engine` | string | **必填**，引擎名：`animetrace` / `saucenao` / `ehentai` / `google` / `yandex` |

---

## 🔧 常见问题

### Q1：哪些引擎需要 API Key？

| 引擎 | 需要配置 |
|------|---------|
| AnimeTrace / Yandex / E-Hentai | 不需要，装好即用 |
| SauceNAO | 建议配置 `api_key`（[免费申请](https://saucenao.com/user.php)，每日 150 次） |
| Google | 需要 [SerpAPI Key](https://serpapi.com/)（推荐）或 Zenserp Key |

### Q2：E-Hentai 搜不了 / 想看 ExHentai 内容？

- E-Hentai 免配置可搜；**ExHentai** 需要账号 Cookie（`ipb_member_id`、`ipb_pass_hash`、`igneous`），填在 `default_params.ehentai.cookies`，并开启 `is_ex`

### Q3：国内服务器搜图很慢 / 搜不到？

在 `proxies` 配置代理（如 `http://127.0.0.1:7890`）。SauceNAO、Google、Yandex 等引擎对国内 IP 有风控，代理是必需的。

### Q4：搜索结果卡片图没生成？

插件优先走 AstrBot 云端文转图（t2i）渲染 HTML 卡片；若云端不可达/超时，**自动降级为内置 PIL 渲染**（仍会出图）。若两者都失败才回退纯文本。升级 AstrBot 到最新版可改善云端渲染稳定性。

### Q5：Yandex / E-Hentai 的 Cookie 怎么获取、填什么？

Cookie 就是浏览器登录网站后自动保存的一段身份凭证。要填的是**一整行 `name1=value1; name2=value2` 格式的字符串**。两种获取方法（任选其一）：

**方法一：控制台一键获取（最简单，先试这个）**
1. 浏览器访问目标网站并**登录**（E-Hentai 用 https://e-hentai.org；ExHentai 用 https://exhentai.org；Yandex 用 https://yandex.com/images）
2. 按 **F12** → 点顶部 **Console（控制台）** 标签页
3. 在下方输入框输入 `document.cookie` 然后**回车**
4. 控制台会直接输出一整行 Cookie 字符串 → **复制它**（形如 `ipb_member_id=123; ipb_pass_hash=abc; ...`）
5. ⚠️ 局限：拿不到 **HttpOnly** 的字段——**E-Hentai 够用**；**Yandex 部分关键字段是 HttpOnly，建议用方法二**

**方法二：Network 面板（完整版，Yandex 建议）**
1. 登录目标网站后按 **F12** → 点 **Network（网络）** 标签页
2. ⚠️ **注意：顶部那个过滤输入框不要填任何东西**（填了会过滤掉请求，列表变空！），保持空白
3. **刷新页面**（F5）→ 左侧出现请求列表 → **点击第一条请求**
4. 右侧打开 **Headers（标头）** → 往下找 **Request Headers（请求标头）** 区域
5. 找到 **`Cookie:`** 开头的那一行 → **复制整行**（`Cookie:` 等号后面的完整内容）

复制的内容形如（值以实际为准）：
```
yandexuid=1587138991653; ymex=1986384493.yrts.159; Session_id=3:163...:0
```
把整行粘贴到插件配置 `default_params.yandex.cookies` / `default_params.ehentai.cookies` 即可。

> 💡 Yandex 反爬严格，不填 Cookie 可能触发验证码导致搜索无结果；E-Hentai 搜索 ExHentai 内容必须填 Cookie（含 `ipb_member_id`、`ipb_pass_hash`、`igneous` 三个关键字段）。从插件实际请求的域名（yandex.com）获取最稳妥。

---

## 📝 更新日志

> 📋 **[查看更新日志 →](CHANGELOG.md)**

---

## ⭐ 支持本项目

如果这个插件对你有帮助，欢迎点亮 Star ⭐，有问题和建议请提交 [Issue](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues) 或 [Pull Request](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/pulls)。

## 🙏 致谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) 开源聊天机器人框架
- [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2) 原始项目

---

## 📜 许可证

本项目采用 **MIT License** 开源协议。

---

## 👤 作者

[@OMSociety](https://github.com/OMSociety)
