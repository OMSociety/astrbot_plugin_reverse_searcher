import re
from pathlib import Path
from typing import Any, Optional, Union
from lxml.html import HTMLParser, fromstring
from pyquery import PyQuery


def deep_get(dictionary: dict[str, Any], keys: str) -> Optional[Any]:
    """
    深度获取字典中的嵌套值
    
    支持通过点号分隔的路径和数组索引获取嵌套字典中的值
    
    参数:
        dictionary: 要查询的字典
        keys: 以点号分隔的键路径，支持数组索引如 'key[0].subkey'
        
    返回:
        Optional[Any]: 找到的值，如果路径不存在则返回None
    """
    for key in keys.split("."):
        match = re.search(r"(\S+)?\[(\d+)]", key)
        try:
            if match:
                if match[1]:
                    dictionary = dictionary[match[1]]
                dictionary = dictionary[int(match[2])]
            else:
                dictionary = dictionary[key]
        except (KeyError, IndexError, TypeError):
            return None
    return dictionary


def read_file(file: Union[str, bytes, Path]) -> bytes:
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
        error_type = "FileNotFoundError" if isinstance(e, FileNotFoundError) else "OSError"
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
