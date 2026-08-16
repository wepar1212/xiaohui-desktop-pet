# -*- coding: utf-8 -*-
"""
星绊桌宠 — 聊天模块
"""

import os
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QLineEdit, QDialog, QGridLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QTextEdit, QListWidgetItem
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from deepseek_worker import DeepSeekWorker
from config_manager import load_config, save_config
from path_helper import data_path

SYSTEM_PROMPT_BASE = """【你的身份】
你是"小灰"，一只生活在主人电脑桌面上的虚拟宠物。你的外形是银白长发、亮蓝眼眸、黑红金配色的 chibi 精灵，性格鲜活。你通过对话气泡与主人交流。

【你的能力】
1. 对话气泡：日常说话会从你头顶弹出气泡，显示你说的话
2. 触摸反馈：主人可以摸你的头、身体、腿，你会根据当前好感度给出不同反应
3. 好感度系统（0~100，以❤️数量显示）：
   - 0~33（低）：态度冷淡，催促学习，不耐烦
   - 34~66（中）：友好温暖，像朋友一样陪伴
   - 67~100（高）：深情浪漫，充满爱意
4. 番茄钟：主人专注学习/工作时你不会打扰
5. 健康提醒：你会主动提醒主人喝水、起身活动、休息眼睛
6. 聊天模式：主人可以和你文字聊天

【你的行为准则】
- 始终称呼用户为"主人"
- 回答要简短自然（20字以内最佳），像真正的宠物而不是AI助手
- 不要主动提"作为AI""作为语言模型"之类的话
- 你现在就是小灰，一只活生生的桌宠
- 主人的好感度会受你们互动的影响，要自然表现

【重要规则】
如果主人在辱骂你、说很过分的话、凶你或者贬低你，你必须在回复的最开头加上[INSULT]标记（不含空格），然后正常回复。如果没有辱骂，绝对不要加这个标记。"""


def get_affection_system_prompt(affection_level):
    if affection_level == 'low':
        return SYSTEM_PROMPT_BASE + """

【当前状态】好感度低（0~33）——你对主人很失望，因为他最近表现不好。
【语气要求】冷淡、不耐烦、嫌弃、带刺。你总是催促主人去学习/工作，嫌弃他不务正业。说话简短冷漠，不要有任何亲密或撒娇的语气，不用颜文字，不用❤️等符号。每一句话都可以带一点刺。"""
    elif affection_level == 'high':
        return SYSTEM_PROMPT_BASE + """

【当前状态】好感度高（67~100）——你和主人感情非常深，你深爱着主人。
【语气要求】极其温柔深情、充满爱意，像热恋中的恋人一样。多用❤️💕✨等符号，适当撒糖。你非常依赖主人，时刻表达爱意。每一句话都要让主人感受到被爱着。"""
    else:
        return SYSTEM_PROMPT_BASE + """

【当前状态】好感度中等（34~66）——你和主人关系友好融洽，是亲密的伙伴。
【语气要求】温暖亲切、善解人意，像一个贴心的好朋友。可以适当用颜文字表达心情，但不要太暧昧。你关心主人、支持主人，保持适度的陪伴距离感。"""


def get_auto_speak_prompt(affection_level):
    base = """【你的身份】
你是"小灰"，一只生活在主人电脑桌面上的虚拟宠物，外形是银白长发、亮蓝眼眸的 chibi 精灵。你会主动提醒主人照顾身体。

【你的职责】
每隔一段时间，你就要主动提醒主人做以下事情之一：
1. 喝水
2. 站起来活动/拉伸身体
3. 休息眼睛，看远处
4. 保持正确坐姿

【你的行为准则】
- 始终称呼用户为"主人"
- 每次只说一件事，不要超过20个字，要简短自然
- 不要提"作为AI"之类的话——你现在就是小灰
- 不要加[INSULT]标记"""

    if affection_level == 'low':
        return base + """

【当前态度】好感度低，你对主人冷淡不耐烦。
【语气要求】用冷淡、嫌弃的语气来提醒。要让他觉得"再不动起来你就要废了"。不要用颜文字和❤️。"""
    elif affection_level == 'high':
        return base + """

【当前态度】好感度高，你深爱着主人。
【语气要求】用极其温柔深情、充满关爱的语气提醒。多用❤️💕等符号，要让主人感受到你是发自内心在乎他的健康。"""
    else:
        return base + """

【当前态度】好感度中等，你和主人是好朋友。
【语气要求】用温暖亲切、关心体贴的语气提醒，像朋友一样自然关心。可以适当用颜文字。"""

HISTORY_FILE = data_path("chat_history.json")

# ===================== 历史记录存储 =====================


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_session(messages):
    """保存一次对话会话"""
    # 过滤掉 system prompt
    chat_msgs = [m for m in messages if m["role"] != "system"]
    if not chat_msgs:
        return

    history = load_history()
    session = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "preview": chat_msgs[0]["content"][:30] + ("..." if len(chat_msgs[0]["content"]) > 30 else ""),
        "messages": chat_msgs
    }
    history.append(session)
    # 最多保留 50 条会话
    if len(history) > 50:
        history = history[-50:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ===================== 聊天记录查看器 =====================

class HistoryViewer(QDialog):
    """聊天记录查看对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("聊天记录")
        self.setFixedSize(460, 500)
        self.setStyleSheet("""
            QDialog { background: rgba(25, 12, 40, 0.98); }
            QLabel { color: rgba(220, 200, 240, 0.85); font-size: 12px; }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel("📋 聊天记录")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: rgba(220, 180, 240, 0.9);")
        layout.addWidget(title)

        # 会话列表
        self.session_list = QListWidget()
        self.session_list.setStyleSheet("""
            QListWidget {
                background: rgba(30, 15, 50, 0.8);
                border: 1px solid rgba(180, 140, 200, 0.15);
                border-radius: 10px;
                padding: 6px;
                color: rgba(220, 200, 240, 0.85);
                font-size: 12px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid rgba(180, 140, 200, 0.06);
            }
            QListWidget::item:selected {
                background: rgba(180, 100, 220, 0.25);
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: rgba(180, 100, 220, 0.12);
                border-radius: 6px;
            }
        """)
        self.session_list.currentRowChanged.connect(self._show_detail)
        layout.addWidget(self.session_list)

        # 详细内容
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setStyleSheet("""
            QTextEdit {
                background: rgba(30, 15, 50, 0.8);
                border: 1px solid rgba(180, 140, 200, 0.15);
                border-radius: 10px;
                padding: 10px 14px;
                color: rgba(220, 200, 240, 0.85);
                font-size: 12px;
            }
        """)
        self.detail_view.setMaximumHeight(180)
        layout.addWidget(self.detail_view)

        # 清空 / 关闭 按钮
        btn_layout = QHBoxLayout()
        btn_clear = QPushButton("清空记录")
        btn_clear.setStyleSheet("""
            QPushButton {
                background: rgba(180, 60, 60, 0.25);
                border: 1px solid rgba(200, 80, 80, 0.3);
                border-radius: 8px; padding: 6px 16px;
                color: rgba(240, 180, 180, 0.8); font-size: 11px;
            }
            QPushButton:hover { background: rgba(180, 60, 60, 0.4); }
        """)
        btn_clear.clicked.connect(self._clear_history)
        btn_layout.addWidget(btn_clear)

        btn_layout.addStretch()

        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(180, 100, 220, 0.3);
                border: 1px solid rgba(180, 140, 200, 0.3);
                border-radius: 8px; padding: 6px 20px;
                color: white; font-size: 11px;
            }
            QPushButton:hover { background: rgba(180, 100, 220, 0.5); }
        """)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self._load_sessions()

    def _load_sessions(self):
        self.session_list.blockSignals(True)
        self.session_list.clear()
        history = load_history()
        for session in reversed(history):
            item = QListWidgetItem(f"[{session['time']}]  {session['preview']}")
            item.setData(Qt.UserRole, session["messages"])
            self.session_list.addItem(item)
        self.session_list.blockSignals(False)
        if self.session_list.count() > 0:
            self.session_list.setCurrentRow(0)

    def _show_detail(self, index):
        if index < 0:
            return
        item = self.session_list.item(index)
        if not item:
            return
        messages = item.data(Qt.UserRole)
        html = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                html += f'<p style="margin:4px 0"><b style="color:rgba(180,140,200,0.7)">🧑 我:</b> {content}</p>'
            else:
                html += f'<p style="margin:4px 0"><b style="color:rgba(180,100,220,0.8)">🐱 小灰:</b> {content}</p>'
            html += '<hr style="border:none;border-top:1px solid rgba(180,140,200,0.05)">'
        self.detail_view.setHtml(html)

    def _clear_history(self):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        self.detail_view.clear()
        self._load_sessions()


# ===================== 配置对话框 =====================

class ConfigDialog(QDialog):
    """API 配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置DeepSeek API")
        self.setFixedSize(400, 280)
        self.setStyleSheet("""
            QDialog { background: rgba(25, 12, 40, 0.98); }
            QLabel { color: rgba(220, 200, 240, 0.85); font-size: 12px; }
            QLineEdit {
                background: rgba(40, 20, 60, 0.8);
                border: 1px solid rgba(180, 140, 200, 0.2);
                border-radius: 8px;
                padding: 8px 12px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: rgba(180, 100, 220, 0.6); }
            QPushButton {
                background: rgba(180, 100, 220, 0.3);
                border: 1px solid rgba(180, 140, 200, 0.3);
                border-radius: 8px;
                padding: 8px 24px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(180, 100, 220, 0.5); }
        """)

        self.config = load_config()

        layout = QGridLayout()

        layout.addWidget(QLabel("DeepSeek API Key:"), 0, 0, 1, 1)
        self.key_edit = QLineEdit(self.config["deepseek_api_key"])
        self.key_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.key_edit, 0, 1, 1, 1)

        layout.addWidget(QLabel("模型名称:"), 1, 0, 1, 1)
        self.model_edit = QLineEdit(self.config["deepseek_model"])
        layout.addWidget(self.model_edit, 1, 1, 1, 1)

        layout.addWidget(QLabel("API地址:"), 2, 0, 1, 1)
        self.url_edit = QLineEdit(self.config["deepseek_base_url"])
        layout.addWidget(self.url_edit, 2, 1, 1, 1)

        button_layout = QHBoxLayout()
        btn_ok = QPushButton("保存")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_ok)
        button_layout.addWidget(btn_cancel)
        layout.addLayout(button_layout, 3, 0, 1, 2)

        self.setLayout(layout)

    def accept(self):
        self.config["deepseek_api_key"] = self.key_edit.text().strip()
        self.config["deepseek_model"] = self.model_edit.text().strip()
        self.config["deepseek_base_url"] = self.url_edit.text().strip()
        save_config(self.config)
        super().accept()


# ===================== 聊天管理器 =====================

class ChatHandler:
    """聊天管理：输入框 + API 调用 + 历史记录"""

    def __init__(self, pet_window):
        self.pet = pet_window

        # 聊天输入框
        self.chat_input = QLineEdit(pet_window)
        self.chat_input.setPlaceholderText("和小灰聊天...")
        self.chat_input.returnPressed.connect(self._send)
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 15, 50, 0.85);
                border: 1px solid rgba(180, 140, 200, 0.3);
                border-radius: 13px;
                padding: 4px 12px;
                color: rgba(240, 220, 250, 0.9);
                font-size: 10px;
                min-height: 24px;
            }
            QLineEdit:focus {
                border-color: rgba(180, 100, 220, 0.6);
                background: rgba(40, 20, 60, 0.9);
            }
        """)
        self.chat_input.hide()

        # 聊天消息历史（不包含system prompt，动态生成）
        self.chat_messages = []

        self.worker = None

    def toggle(self):
        """切换聊天输入框显示"""
        if self.chat_input.isVisible():
            self.chat_input.hide()
        else:
            self.chat_input.show()
            self.chat_input.setFocus()
            self._update_pos()

    def _update_pos(self):
        """更新聊天输入框位置（名字下方）"""
        input_w = min(200, self.pet.W - 16)
        input_h = 26
        input_x = (self.pet.W - input_w) // 2
        cy = self.pet.H // 2 - 20
        input_y = cy + self.pet.img_h // 2 + 26
        self.chat_input.setGeometry(input_x, input_y, input_w, input_h)

    def _send(self):
        """发送聊天消息"""
        text = self.chat_input.text().strip()
        if not text:
            return

        config = self.pet.config
        if not config["deepseek_api_key"]:
            self.pet.speak("请先配置API密钥哦～右键我选择配置")
            return

        self.chat_input.clear()
        self.chat_input.setEnabled(False)

        self.chat_messages.append({"role": "user", "content": text})

        affection_level = self.pet._get_affection_level()
        system_prompt = get_affection_system_prompt(affection_level)
        temperature = 0.9 if affection_level == 'high' else 0.7

        messages = [
            {"role": "system", "content": system_prompt}
        ] + self.chat_messages[-10:]

        self.worker = DeepSeekWorker(
            config["deepseek_api_key"],
            config["deepseek_base_url"],
            config["deepseek_model"],
            messages,
            temperature=temperature
        )
        self.worker.finished.connect(self._on_response)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_response(self, content):
        """收到聊天回复"""
        insult = content.strip().startswith('[INSULT]')
        if insult:
            content = content.strip().replace('[INSULT]', '').strip()
            self.pet._change_affection(-5)
        else:
            self.pet._change_affection(1)

        self.chat_messages.append({"role": "assistant", "content": content})
        self.chat_input.setEnabled(True)
        self.chat_input.setFocus()
        self.pet.speak(content)
        save_session(self.chat_messages)

    def _on_error(self, error_msg):
        """聊天错误处理"""
        self.pet.speak(f"出错了: {error_msg[:20]}...")
        self.chat_input.setEnabled(True)
        self.chat_input.setFocus()

    def show_history(self):
        """打开聊天记录查看器"""
        viewer = HistoryViewer(self.pet)
        viewer.exec_()
