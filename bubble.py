# -*- coding: utf-8 -*-
"""小灰的白色极简对话气泡。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QLabel, QGraphicsDropShadowEffect


class Bubble(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMaximumWidth(270)
        self.setFont(QFont("Microsoft YaHei", 11))
        self.setStyleSheet("""
            QLabel {
                color: #171717;
                background: rgba(255, 255, 255, 248);
                border: 1px solid #deded9;
                border-radius: 14px;
                padding: 10px 15px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 35))
        self.setGraphicsEffect(shadow)
        self.hide()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isHidden():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(210, 210, 205, 230), 1))
        path = QPainterPath()
        mid = self.width() // 2
        bottom = self.height() - 1
        path.moveTo(mid - 8, bottom)
        path.lineTo(mid, bottom + 8)
        path.lineTo(mid + 8, bottom)
        path.closeSubpath()
        painter.drawPath(path)
