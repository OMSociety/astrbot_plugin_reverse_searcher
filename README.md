# 图片反搜助手

[![Version](https://img.shields.io/badge/version-v1.3.0-blue.svg)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

支持 AnimeTrace、E-Hentai、Google Lens、Yandex、SauceNAO 五大引擎的图片反向搜索。搜索结果自动渲染为精美卡片图片，同时提供 LLM 主动搜图工具。

> 本项目由AI编写，部分源码基于 [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2) 。

[快速开始](#-快速开始) • [搜索引擎](#-支持的搜索引擎) • [配置项](#-配置项说明) • [LLM 工具](#-llm-可调用工具) • [更新日志](CHANGELOG.md)

---

## 📖 功能概览

### 核心能力
- **五大搜索引擎** — AnimeTrace 认角色、SauceNAO 找出处、Google Lens 综合兜底、Yandex 找相似、E-Hentai 搜本子，各司其职
- **关键词触发** — 发送 `以图搜图` + 图片即可搜，支持引擎别名快捷指定（`a`/`s`/`e`/`g`/`y`）
- **LLM 主动搜图** — 芙兰根据对话意图自主判断何时搜图、用哪个引擎，无需手动指令
- **意图路由** — 基于关键词加权匹配自动选择最优引擎，用户说「这是谁」自动走 AnimeTrace

### 搜索结果卡片
搜索结果不是干巴巴的文字，而是自动生成为一张精美卡片图片：

- 🎨 **引擎主题色顶栏 + 左侧装饰条** — 靛蓝紫 / 暗炭黑 / 绯红，哪家搜的一眼认出
- 🖼️ **源图 + 结果缩略图同框** — 待搜索图片和匹配结果并列展示，缩略图自动保持宽高比
- 📊 **相似度彩色进度条** — ≥90% 绿 / ≥70% 橙 / <70% 红，直观
- 🤖 **AI 检测徽章** — AnimeTrace 结果直接标注是否 AI 生成
---

## 🚀 快速开始

### 安装

**方式一：插件市场**
- AstrBot WebUI → 插件市场 → 搜索 `astrbot_plugin_reverse_searcher`

**方式二：GitHub 仓库**
- AstrBot WebUI → 插件管理 → ＋ 安装
- 粘贴仓库地址：`https://github.com/OMSociety/astrbot_plugin_reverse_searcher`

### 依赖安装
```bash
pip install -r requirements.txt
```
核心依赖：`httpx`, `Pillow`, `pyquery`, `typing_extensions`

---

## 🔍 支持的搜索引擎

| 引擎 | 说明 | 备注 |
|:----|:----|:----|
| **animetrace** | 动漫角色识别 | 无需 API Key，返回作品名+角色名 |
| **saucenao** | 综合出处搜索 | 免费 Key 够用，Pixiv 插画首选 |
| **google** | Google Lens | 需 SerpAPI Key（推荐），综合搜索兜底 |
| **yandex** | 相似图片搜索 | 无需配置 |
| **ehentai** | E-Hentai/ExHentai | 仅 ExHentai 需要 Cookie |

---

## ⚙️ 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `enable_keyword_trigger` | bool | `true` | 关闭后不再响应关键词，但 LLM 工具仍可用 |
| `serpapi_key` | string | - | SerpAPI Key，从 [serpapi.com](https://serpapi.com/) 申请 |
| `zenserp_key` | string | - | 备用 SerpAPI，从 [zenserp.com](https://zenserp.com/) 申请 |
| `api_key` | string | - | SauceNAO API Key，从 [saucenao.com](https://saucenao.com/user.php) 申请 |
| `cookies` | string | - | 仅使用 ExHentai 时需要 |
| `proxies` | string | - | 代理服务器地址 |
| `auto_send_text_results` | bool | `false` | 搜索完成后自动发送文本结果 |

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

## 🛠️ LLM 可调用工具

### reverse_search
通用搜图工具，自动判断引擎。

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_base64` | string | 图片 base64 编码（可选） |
| `image_url` | string | 图片 URL（可选，与 base64 二选一） |
| `intent` | string | 搜索意图（如「找角色」「找出处」），用于自动选引擎 |

### reverse_search_with_engine
指定引擎搜图。

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_base64` / `image_url` | string | 图片来源 |
| `engine` | string | **必填**，引擎名称 |

---

## 📝 更新日志

> 📋 **[查看完整更新日志 →](CHANGELOG.md)**

---

## 🤝 贡献与反馈

如遇问题请在 [GitHub Issues](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues) 提交，欢迎 Pull Request！

---

## 📜 许可证

本项目采用 **MIT License** 开源协议。

---

## 👤 作者

**Slandre & Flandre** — [@OMSociety](https://github.com/OMSociety)
