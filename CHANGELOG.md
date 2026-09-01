# Changelog

## [1.0.2] - 2026-09-01

### 🐛 Bug 修复

- **修复 GoogleLens 引擎代理/超时配置失效 + HTTP client 泄漏**：GoogleLens 编排器及其子引擎（SerpApi / Zenserp）在构造时丢弃了共享的 Network 连接，导致代理与超时配置对 Google 引擎不生效，且每次搜索会新建 3 个不关闭的 httpx client。现已正确转发共享连接
- **修复测试无法收集**：`tests/conftest.py` 缺 `sys.path` 注入、`test_security.py` 路径写错，导致 `pytest` 报 `No module named 'ReverseSearcher'`。已补齐（52 个用例现已可运行）

### 🧹 代码清理

- 移除死代码：`BaseSearchModel.search_and_print`（含控制台 print）、`_prepare_engine_params` 的 `ascii2d` 空分支及其测试
- 清理 `yandex_req.py` / `google_lens_parser.py` 中过时的 "HandOver / requests" 注释与内联 `import`，统一提升到模块顶部
- 新增 `ruff.toml` 统一代码规范（与 MaiBot 版一致的豁免策略）

### ⚡ 性能优化

- **DNS 解析不再阻塞事件循环**：`is_safe_image_url` 的域名解析加入进程级缓存（TTL 5 分钟），并在所有异步调用点用 `asyncio.to_thread` 挪出事件循环线程，消除 SSRF 校验时的同步 DNS 阻塞

## [1.0.1] - 2026-08-16

### 🔒 安全修复

- **修复任意本地文件读取漏洞**：图片本地路径仅允许 AstrBot 数据目录内（如 `data/temp/`），拒绝读取任意本地文件（消息内容 `path /xxx` 写法与 LLM `image_url` 参数均受限）
- **修复 SSRF（服务端请求伪造）漏洞**：图片 URL 仅允许公网 http/https，拒绝内网 / 环回 / 链路本地 / 云元数据 / 保留地址，并做 DNS 解析二次校验（防 DNS rebinding）
- **修复重定向型 SSRF**：图片下载改为手动逐跳校验重定向，公网 URL 跳转到内网地址时拦截
- **新增安全校验模块** `ReverseSearcher/utils/security.py`，统一所有图片引用入口（消息图片、文本 URL、LLM 工具参数、引擎 url）的安全校验

### 🧪 测试

- 新增 22 个安全测试用例：内网 IP 判定矩阵、DNS rebinding 防护、本地路径目录白名单、`file://` 协议拒绝等

### ⚠️ 行为变化

- 内网图片地址、任意本地路径、`file://` 协议将被拒绝并提示"仅支持公网图片 URL 或消息内图片"
- 正常使用不受影响：消息直接发图（QQ 官方预下载到 `data/temp/`）、公网图床 URL 均正常
