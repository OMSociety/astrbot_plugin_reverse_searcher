from pathlib import Path

from lxml.html import HTMLParser, fromstring
from pyquery import PyQuery


def read_file(file: str | bytes | Path) -> bytes:
    """
    读取文件内容为字节数据

    参数:
        file: 文件路径或字节数据

    返回:
        bytes: 文件的字节内容

    异常:
        FileNotFoundError: 当文件不存在时抛出
        OSError: 当文件读取出错时抛出
    """
    if isinstance(file, bytes):
        return file
    try:
        return Path(file).read_bytes()
    except (FileNotFoundError, OSError) as e:
        error_type = (
            "FileNotFoundError" if isinstance(e, FileNotFoundError) else "OSError"
        )
        raise type(e)(f"{error_type}：读取文件 {file} 时出错: {e}") from e


def parse_html(html: str) -> PyQuery:
    """
    解析HTML字符串为PyQuery对象

    参数:
        html: HTML字符串

    返回:
        PyQuery: 解析后的PyQuery对象，用于CSS选择器查询
    """
    utf8_parser = HTMLParser(encoding="utf-8")
    return PyQuery(fromstring(html, parser=utf8_parser))
