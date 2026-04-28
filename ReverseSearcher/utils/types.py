from pathlib import Path

# 类型别名定义
FilePath = str | Path
FileContent = str | bytes | FilePath | None
