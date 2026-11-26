"""业务异常定义。

独立成模块，供 services / policies 等共同引用，避免循环导入。
"""
from __future__ import annotations


class BusinessError(Exception):
    """业务规则违反异常，携带面向用户的提示。"""
