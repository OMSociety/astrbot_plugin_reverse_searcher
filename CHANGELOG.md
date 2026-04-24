# Changelog

> 本项目仍处于活跃维护中。

---

## [1.0.1] - 2026-04-XX

### 新增
- 支持多引擎搜索：animetrace / saucenao / ehentai / google / yandex

### 修复
- 修复图片编码相关问题

---

## [1.0.0] - 2026-04-23

### 初始版本
- **LLM 主动搜图工具**：可自主判断何时搜图、用哪个引擎
  - `reverse_search`：通用搜图，自动判断引擎
  - `reverse_search_with_engine`：指定引擎搜图
- **关键词触发开关**：`enable_keyword_trigger` 配置项，可关闭 `以图搜图` 等关键词响应