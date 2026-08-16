# -*- coding: utf-8 -*-
"""小灰桌宠的 Codex Pet 极简白色主题。"""

from PyQt5.QtGui import QColor


BG = "#f7f7f5"
PANEL = "#ffffff"
PANEL_ALT = "#f0f0ed"
TEXT = "#171717"
MUTED = "#747474"
PURPLE = "#222222"
CYAN = "#555555"
PINK = "#c95b7a"
GOLD = "#9b741f"
DANGER = "#b8475d"


def rgba(color, alpha):
    q = QColor(color)
    q.setAlpha(alpha)
    return q


def app_stylesheet():
    return f"""
    QWidget {{
        color: {TEXT};
        font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    }}
    QDialog {{
        background: {BG};
    }}
    QLabel#eyebrow {{
        color: #767676;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2px;
    }}
    QLabel#title {{
        color: {TEXT};
        font-size: 22px;
        font-weight: 700;
    }}
    QLabel#subtitle {{
        color: {MUTED};
        font-size: 12px;
    }}
    QLabel#section {{
        color: #606060;
        font-size: 11px;
        font-weight: 700;
    }}
    QFrame#card {{
        background: {PANEL};
        border: 1px solid #e7e7e3;
        border-radius: 16px;
    }}
    QFrame#statusCard {{
        background: #ffffff;
        border: 1px solid #deded9;
        border-radius: 16px;
    }}
    QPushButton {{
        background: {PANEL_ALT};
        border: 1px solid #e2e2de;
        border-radius: 10px;
        color: {TEXT};
        font-size: 12px;
        padding: 10px 14px;
    }}
    QPushButton:hover {{
        background: #e5e5e1;
        border-color: #bcbcb7;
    }}
    QPushButton:pressed {{
        background: #d8d8d3;
    }}
    QPushButton#accent {{
        background: #171717;
        border: 1px solid #171717;
        color: white;
        font-weight: 700;
    }}
    QPushButton#accent:hover {{
        background: #3b3b3b;
    }}
    QPushButton#quiet {{
        background: transparent;
        border-color: #e4e4df;
        color: #666666;
    }}
    QLineEdit, QTextEdit, QListWidget, QComboBox {{
        background: {PANEL};
        border: 1px solid #dfdfda;
        border-radius: 10px;
        color: {TEXT};
        padding: 9px 11px;
        selection-background-color: #dcdcd6;
        selection-color: #111111;
    }}
    QLineEdit:focus, QTextEdit:focus, QListWidget:focus {{
        border-color: #888883;
    }}
    QProgressBar {{
        background: #ecece8;
        border: none;
        border-radius: 5px;
        min-height: 9px;
        max-height: 9px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: #202020;
        border-radius: 5px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #c6c6c0;
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0px;
    }}
    QToolTip {{
        background: #171717;
        border: none;
        color: white;
        padding: 6px 8px;
    }}
    """

def card_style(object_name="card"):
    return f"""
        QFrame#{object_name} {{
            background: {PANEL};
            border: 1px solid #e7e7e3;
            border-radius: 16px;
        }}
    """

