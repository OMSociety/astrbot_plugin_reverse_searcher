# Changelog

本项目所有重要更改都会记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-09-13

### ✨ 新增

- **WebUI 四语本地化**：新增 `zh-CN` / `en-US` / `ru-RU` / `ja-JP` 四份 i18n 文件（`.astrbot-plugin/i18n/`），插件名、简介与全部 66 条配置项文案在四种界面语言下均正确显示；中文文案与配置 schema 保持逐字镜像。默认触发词「以图搜图」等必须保留的中文字面量在各语言中维持原文。
- README 新增多语言版本（English / Русский / 日本語），顶部提供语言导航，并修正与代码不符的功能描述。

## [1.0.5] - 2026-09-07

### ⚙️ 变更

- **下载链路 SSRF 加固**：`download()` 首跳不再依赖调用方自查，逐跳校验补齐；`search_and_draw` 的 URL 入口补安全校验（与 `search()` 对齐）。
- DNS 结果缓存增加 512 条上限保底；E-Hentai 标签翻译表改为按路径缓存（不再每次显示结果重读磁盘）；SerpApi 请求不再发送空的 `q=` 参数。
- 移除 `get_img_urls` 中不可达的组件 repr 扫描段（标准组件链与 raw_message 兜底保留，行为不变）。

## [1.0.4] - 2026-09-06

### 🐛 修复

- **修复引用回复取图**：旧实现依赖当前框架不存在的 `event.raw_event` 属性，"回复一张图 → 搜图"实际取不到图。现改为遍历标准组件链中的 `Reply` 组件、从其 `chain` 提取图片（aiocqhttp 适配器自动填充被引用消息内容）。
- 修复 LLM 搜图工具"从消息上下文提图"读取不存在字段导致永远返回空的问题，改读真实组件链（含引用回复）。
- 搜索失败卡片现在显示具体原因（含 api_key 脱敏），不再只有笼统的"搜索失败"。

### ⚙️ 变更

- 结果缩略图由串行下载改为并发下载。
- 移除已无调用的死代码（引擎注册表候补字段/意图辅助方法、消息状态冗余分支等约 200 行），三个相同的等待处理器合并为一个（行为不变）。

## [1.0.3] - 2026-09-01

### 🔒 安全

- **修复重定向型 SSRF 绕过（Network 客户端）**：`Network` 的 httpx 客户端此前 `follow_redirects=True`，只校验初始 URL、未校验重定向目标。现改为 `download()` 手动逐跳跟随并对每一跳重新校验（`is_safe_image_url`，最多 3 跳），公网 URL 302 到内网（`169.254.169.254` 等）会被拦截
- **修复 HTML 注入**：搜索引擎返回的 `title/url/author/error_msg` 是第三方内容，此前直接拼进 HTML 模板再交给云端 t2i。现于渲染前用 `html.escape` 逐字段转义（云端渲染器是否转义不受控），防止被当作 HTML/脚本渲染

### ⚙️ 变更

- **新增 `allow_third_party_image_host` 开关**（默认 `true`）：允许把本地图上传到第三方临时图床（`tmpfiles.org` / `uguu.se` / `litterbox.catbox.moe` / `tmp.ninja`）。关闭后 Google/Yandex 本地图搜不可用，需改用图片 URL
- README 新增「隐私披露」：明确说明本地图搜 Google/Yandex 时图片会先上传到上述临时图床、保留时长由第三方决定、如何关闭

## [1.0.2] - 2026-09-01

### 🐛 修复

- **修复 GoogleLens 引擎代理/超时配置失效 + HTTP client 泄漏**：GoogleLens 编排器及其子引擎（SerpApi / Zenserp）在构造时丢弃了共享的 Network 连接，导致代理与超时配置对 Google 引擎不生效，且每次搜索会新建 3 个不关闭的 httpx client。现已正确转发共享连接
- **修复测试无法收集**：`tests/conftest.py` 缺 `sys.path` 注入、`test_security.py` 路径写错，导致 `pytest` 报 `No module named 'ReverseSearcher'`。已补齐（52 个用例现已可运行）

### ⚙️ 变更

- 移除死代码：`BaseSearchModel.search_and_print`（含控制台 print）、`_prepare_engine_params` 的 `ascii2d` 空分支及其测试
- 清理 `yandex_req.py` / `google_lens_parser.py` 中过时的 "HandOver / requests" 注释与内联 `import`，统一提升到模块顶部
- 新增 `ruff.toml` 统一代码规范（与 MaiBot 版一致的豁免策略）
- **DNS 解析不再阻塞事件循环**：`is_safe_image_url` 的域名解析加入进程级缓存（TTL 5 分钟），并在所有异步调用点用 `asyncio.to_thread` 挪出事件循环线程，消除 SSRF 校验时的同步 DNS 阻塞

## [1.0.1] - 2026-08-16

### 🔒 安全

- **修复任意本地文件读取漏洞**：图片本地路径仅允许 AstrBot 数据目录内（如 `data/temp/`），拒绝读取任意本地文件（消息内容 `path /xxx` 写法与 LLM `image_url` 参数均受限）
- **修复 SSRF（服务端请求伪造）漏洞**：图片 URL 仅允许公网 http/https，拒绝内网 / 环回 / 链路本地 / 云元数据 / 保留地址，并做 DNS 解析二次校验（防 DNS rebinding）
- **修复重定向型 SSRF**：图片下载改为手动逐跳校验重定向，公网 URL 跳转到内网地址时拦截
- **新增安全校验模块** `ReverseSearcher/utils/security.py`，统一所有图片引用入口（消息图片、文本 URL、LLM 工具参数、引擎 url）的安全校验

### ✨ 新增

- 新增 22 个安全测试用例：内网 IP 判定矩阵、DNS rebinding 防护、本地路径目录白名单、`file://` 协议拒绝等

### ⚙️ 变更

- 内网图片地址、任意本地路径、`file://` 协议将被拒绝并提示"仅支持公网图片 URL 或消息内图片"
- 正常使用不受影响：消息直接发图（QQ 官方预下载到 `data/temp/`）、公网图床 URL 均正常
