#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小灰桌宠 v2 启动入口。"""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor
from PyQt5.QtWidgets import QApplication

from pet_window import XiaoHuiPet
from ui_theme import BG


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("小灰桌宠")
    app.setApplicationDisplayName("小灰 · 桌面陪伴")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.Base, QColor(BG))
    palette.setColor(QPalette.Text, QColor("#f7f3ff"))
    palette.setColor(QPalette.WindowText, QColor("#f7f3ff"))
    app.setPalette(palette)
    app.setFont(QFont("Microsoft YaHei", 10))

    pet = XiaoHuiPet()
    pet.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
