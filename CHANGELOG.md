# Changelog

> 本项目仍处于活跃维护中。

---

## [1.2.0] - 2026-04-27

### 🎨 搜索结果图片全面重做
- **全新卡片式渲染**：`ResultCardRenderer` 从零重写，纯 PIL 手绘，不再依赖外部渲染库
  - 渐变引擎色顶栏、圆角卡片、阴影效果
  - 源图缩略图预览 + 结果缩略图展示
  - 相似度彩色进度条（绿 ≥90% / 橙 ≥70% / 红 <70%）
  - 支持作者、标题、来源、链接等完整信息展示
- **错误提示也卡片化**：搜索失败时也生成统一风格卡片，而非生硬文字

### 🐛 Bug 修复
- **E-Hentai 搜索崩溃**：修复 `Union` 类型在 Python 3.10+ 的兼容性问题（`types.UnionType` not callable）
- **E-Hentai 空结果误判**：修复 `.itg` 子元素 `.items()` 生成器恒为 truthy 导致空结果仍尝试解析的问题，先转 `list` 再判空
- **Network 参数传递**：修复 `Network(client=)` 外部复用 client 时参数传递错误
- **配置 schema**：修复 `_conf_schema.json` 中 `type: "boolean"` 应为 `"bool"` 的 JSON Schema 规范问题
- **LLM 工具本地图片**：修复 `path /xxx/xxx.jpg` 格式的本地路径在工具中的解析逻辑
- **AnimeTrace 空结果**：修复 AnimeTrace 返回空结果时解析异常

### 🧹 架构清理
- **删除死代码**：移除不再使用的 `image_collector.py` 和未引用的 `deep_get` 工具函数
- **精简 main.py**：清理冗余逻辑，统一搜索解析器 `_resolve_and_search` 收敛三个等待处理器
- **引擎注册中心**：引入 `EngineDef` dataclass 和 `IntentRouter`，引擎元数据单一数据源
- **硬编码消除**：触发关键词、引擎关键词等全部移至配置文件可自定义

### 🔧 工具层改进
- **LLM 搜图工具**：支持 `reverse_search`（自动选引擎）和 `reverse_search_with_engine`（指定引擎）双工具
- **意图路由**：基于关键词加权匹配自动选择最优引擎
- **源码图预览**：搜索结果卡片中包含待搜索图片的缩略图

---

## [1.1.0] - 2026-04-26

### 配置优化
- **AnimeTrace 布尔开关**：将 `is_multi` 和 `ai_detect` 从整数改为布尔开关，前端直接显示开关控件，后端自动转换为 `0/1` 参数
- **超时配置细化**：新增 `timeout_settings` 配置分组，包含搜索参数等待超时和结果确认超时

---

## [1.0.0] - 2026-04-23
