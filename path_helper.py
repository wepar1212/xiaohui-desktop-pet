# -*- coding: utf-8 -*-
"""
星绊桌宠 — 路径工具（兼容 PyInstaller 打包）
"""

import sys
import os


def resource_path(relative_path):
    """返回打包在 exe 内部的资源路径（图片等只读文件）"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def data_path(relative_path):
    """返回可读写的数据文件路径（config / 聊天记录），放在 exe 同目录"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)
