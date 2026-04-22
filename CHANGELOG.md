# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-23

### Added
- **LLM 主动搜图工具**：芙兰可自主判断何时搜图、用哪个引擎
  - `reverse_search`：通用搜图，自动判断引擎（animetrace/saucenao/ehentai/google/yandex）
  - `reverse_search_with_engine`：指定引擎搜图
- **关键词触发开关**：`enable_keyword_trigger` 配置项，可关闭 `以图搜图` 等关键词响应

### Fixed
- 修复 `model.py` 中 `search()` 方法的重复代码块导致结果解析失败
- 修复 `saucenao api_key` pop 缺少默认值导致无 key 时崩溃
- 修复 `state_handlers` 字典重复键值
- 修复 `_handle_waiting_image` 未定义 `message_text` 变量
- 修复 `_handle_waiting_text_confirm` else 缩进错误
- 修复 `_check_and_ask_mode` 空方法（只有 `return; return`）
- 修复 `main.py` 字体路径错误（`ReverseSearcher/resource` → `resource`）
- 修复 filter 监听类型从 `ALL` 改为 `PRIVATE_MESSAGE`
- 修复 `search_tools.py` 缺少 `ReverseSearchTool` 类定义（重构时误删）

### Refactored
- 移除 `copyseeker` 死代码（ENGINE_MAP 中不存在）
- 改进工具注册日志输出，使用 `logger` 而非 `stderr`
- `search_tools.py` 图片获取逻辑增强：支持从 `context.messages` 获取图片

### Infrastructure
- 引擎名映射 `animetrace` → `AnimeTrace` 类（修复 KeyError）