# -*- coding: utf-8 -*-
"""小灰桌宠主窗口：v2 图集动画、视线方向与玻璃拟态 GUI。"""

import math
import random

from PyQt5.QtCore import QPoint, QRect, Qt, QTimer
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPixmap,
    QCursor,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bubble import Bubble
from chat import get_affection_system_prompt, load_history, save_session
from config_manager import load_config, save_config
from deepseek_worker import DeepSeekWorker
from dialogues import (
    AFFECTION_DOWN_REPLIES,
    AFFECTION_UP_REPLIES,
    BODY_REPLIES,
    BODY_REPLIES_HIGH,
    BODY_REPLIES_LOW,
    LEG_REPLIES,
    LEG_REPLIES_HIGH,
    LEG_REPLIES_LOW,
    LINES,
    PET_REPLIES,
    PET_REPLIES_HIGH,
    PET_REPLIES_LOW,
    POMO_REPLIES,
)
from path_helper import resource_path
from pomodoro import PomodoroTimer
from ui_theme import (
    CYAN,
    MUTED,
    PANEL,
    PURPLE,
    TEXT,
    app_stylesheet,
)


class XiaoHuiPet(QWidget):
    """悬浮桌宠：使用 8×11 v2 图集，自动根据鼠标方向切换视线。"""

    CELL_W = 192
    CELL_H = 208
    SLEEPY_DURATION_TICKS = 125  # 80ms 一帧，约 10 秒
    ATLAS_ROWS = {
        "idle": 0,
        "running-right": 1,
        "running-left": 2,
        "waving": 3,
        "jumping": 4,
        "failed": 5,
        "sleepy": 5,
        "waiting": 6,
        "running": 7,
        "review": 8,
    }
    DIRECTION_NAMES = (
        "上方",
        "右上",
        "右上",
        "右上",
        "右侧",
        "右下",
        "右下",
        "右下",
        "下方",
        "左下",
        "左下",
        "左下",
        "左侧",
        "左上",
        "左上",
        "左上",
    )
    TOUCH_LINES = {
        "head": PET_REPLIES,
        "body": BODY_REPLIES,
        "leg": LEG_REPLIES,
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("小灰 · 桌面陪伴")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.W = 280
        self.H = 400
        self.resize(self.W, self.H)

        self._dragging = False
        self._drag_offset = QPoint()
        self._press_pos = QPoint()
        self._time = 0
        self._frame = 0
        self._pose_ticks = 0
        self._pose = "idle"
        self._speaking = False
        self._direction = 0
        self._gaze_ticks_left = 0
        self._gaze_cooldown = random.randint(90, 150)
        self._gaze_return_pose = "idle"
        self._click_gaze_pending = False
        self._waiting_reason = None
        self._waiting_ticks_left = 0
        self._pending_waiting = None
        self._thinking_active = False
        self._pet_rot = 0.0
        self._pet_timer = 0
        self._bounce = 0.0
        self._last_pixmap = None
        self._idle_cycle_counter = 0
        self._drag_direction = 0
        self._drag_last_pos = QPoint()
        self._drag_pose = None
        self._chat_dialog = None
        self._control_panel = None

        self.config = load_config()
        self._affection = max(0, min(100, self.config.get("affection", 40)))
        self.AFFECTION_MAX = 100

        self._load_atlas()

        self.bubble = Bubble(self)
        self.bubble.hide()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_bubble)

        pomo_minutes = self.config.get("pomodoro_minutes", 25)
        self.pomodoro = PomodoroTimer(
            on_tick=self._pomodoro_tick,
            on_done=self._pomodoro_done,
            work_minutes=pomo_minutes,
        )

        self._auto_talk_level = self.config.get("auto_talk_level", 2)
        self._auto_talk_timer = None
        self._rebuild_auto_talk()

        self._build_menu()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(80)

        self._place_initial()
        QTimer.singleShot(650, lambda: self.speak("主人，我带着新方向回来啦。"))

    # -------------------- v2 图集 --------------------

    def _load_atlas(self):
        atlas = QPixmap(resource_path("spritesheet.webp"))
        if atlas.isNull():
            raise FileNotFoundError("找不到 v2 图集 spritesheet.webp")

        self.frames = {}
        for name, row in self.ATLAS_ROWS.items():
            frames = [
                atlas.copy(col * self.CELL_W, row * self.CELL_H, self.CELL_W, self.CELL_H)
                for col in range(8)
            ]
            # 个别旧图集行尾可能是完全透明的占位格。过滤掉它们，避免动画播放到空帧。
            visible_frames = [frame for frame in frames if self._pixmap_has_visible_pixels(frame)]
            self.frames[name] = visible_frames or frames[:1]

        self.look_frames = []
        last_look_frame = self.frames["idle"][0]
        for row, start in ((9, 0), (10, 8)):
            for col in range(8):
                frame = atlas.copy(col * self.CELL_W, row * self.CELL_H, self.CELL_W, self.CELL_H)
                if self._pixmap_has_visible_pixels(frame):
                    last_look_frame = frame
                else:
                    frame = last_look_frame
                self.look_frames.append(frame)

        # v2 图集单元格按原先显示尺寸的二分之一渲染。
        self.sprite_scale = 0.69
        self.sprite_w = int(self.CELL_W * self.sprite_scale)
        self.sprite_h = int(self.CELL_H * self.sprite_scale)
        self.sprite_top = 112
        self.sprite_rect = QRect(
            (self.W - self.sprite_w) // 2,
            self.sprite_top,
            self.sprite_w,
            self.sprite_h,
        )

    @staticmethod
    def _pixmap_has_visible_pixels(pixmap):
        image = pixmap.toImage()
        if image.isNull() or not image.hasAlphaChannel():
            return not pixmap.isNull()
        for y in range(image.height()):
            for x in range(image.width()):
                if image.pixelColor(x, y).alpha() > 0:
                    return True
        return False

    def _current_pixmap(self):
        if self._pose == "look":
            pixmap = self.look_frames[self._direction]
        else:
            frames = self.frames.get(self._pose, self.frames["idle"])
            pixmap = frames[self._frame % len(frames)]
        if pixmap.isNull() and self._last_pixmap is not None:
            return self._last_pixmap
        self._last_pixmap = pixmap
        return pixmap

    def _set_pose(self, pose):
        if pose not in self.frames and pose != "look":
            pose = "look"
        self._pose = pose
        self._frame = 0
        self._pose_ticks = 0
        if pose != "look":
            self._gaze_ticks_left = 0
        if pose not in {"idle", "look"}:
            self._idle_cycle_counter = 0
        if pose not in {"waiting", "sleepy"}:
            self._waiting_reason = None
            self._waiting_ticks_left = 0
        self.update()

    def _start_waiting(self, reason, duration_ticks=0):
        """进入 waiting 分支；0 表示直到对应条件结束，否则为短暂提示。"""
        self._waiting_reason = reason
        self._waiting_ticks_left = max(0, duration_ticks)
        self._set_pose("sleepy" if reason == "sleepy" else "waiting")

    def _clear_waiting(self, reason=None):
        if reason is not None and self._waiting_reason != reason:
            return
        self._waiting_reason = None
        self._waiting_ticks_left = 0
        self._sync_state_pose()

    def _state_pose(self, state=None):
        state = state or self.pomodoro.state
        return {
            "working": "running",
            "paused": "waiting",
            "break": "idle",
            "idle": "idle",
        }.get(state, "idle")

    def _start_gaze(self, duration_ticks=62, forced=False):
        """采样一次鼠标方向并保持约 5 秒，之后恢复触发前的主体动画。"""
        if self._speaking or self._dragging:
            return False
        self._gaze_return_pose = self._state_pose()
        self._set_pose("look")
        self._update_direction()
        self._gaze_ticks_left = max(1, duration_ticks)
        self._gaze_cooldown = 0 if forced else random.randint(105, 180)
        return True

    def _sync_state_pose(self):
        """只在没有临时动作时，根据番茄钟状态恢复主体动画。"""
        if self._speaking or self._dragging:
            return
        if self._thinking_active:
            if self._pose != "waiting":
                self._start_waiting("thinking")
            return
        # 有效视线动作期间不要被番茄钟的每秒刷新打断。
        if self._pose == "look" and self._gaze_ticks_left > 0:
            return
        if self.pomodoro.state == "paused":
            if self._waiting_reason == "paused" and self._pose == "waiting":
                return
            self._start_waiting("paused")
            return
        if self._waiting_reason == "break_intro" and self._waiting_ticks_left > 0:
            return
        if (
            self._waiting_reason == "sleepy"
            and self._pose == "sleepy"
            and self._waiting_ticks_left > 0
        ):
            return
        if self._waiting_reason is not None:
            self._waiting_reason = None
            self._waiting_ticks_left = 0
        target = self._state_pose()
        # 番茄钟每秒回调一次；空闲时不要打断正在进行的短暂视线动作。
        if target == "idle" and self._pose in {"idle", "look"}:
            return
        self._set_pose(target)

    def _restore_idle_pose(self):
        if not self._speaking and not self._dragging and self.pomodoro.state == "idle":
            self._gaze_cooldown = random.randint(75, 120)
            self._clear_waiting()
            self._set_pose("idle")

    # -------------------- 视线方向 --------------------

    def _update_direction(self):
        # look 持续期间持续采样鼠标方向，普通待机和其他动作不追踪。
        if self._dragging or self._pose != "look":
            return
        # 以头部附近为旋转中心，比整只身体的几何中心更符合视觉直觉。
        head_center_y = self.sprite_top + int(self.sprite_h * 0.36)
        center = self.mapToGlobal(QPoint(self.W // 2, head_center_y))
        cursor = QCursor.pos()
        dx = cursor.x() - center.x()
        dy = cursor.y() - center.y()
        if abs(dx) + abs(dy) < 8:
            return

        angle = math.degrees(math.atan2(dx, -dy)) % 360
        self._direction = int((angle + 11.25) // 22.5) % 16

    @property
    def direction_label(self):
        return self.DIRECTION_NAMES[self._direction]

    # -------------------- 好感度与陪伴 --------------------

    def _get_affection_level(self):
        if self._affection <= 33:
            return "low"
        if self._affection <= 66:
            return "mid"
        return "high"

    def _get_hearts_filled(self):
        return round(self._affection / 100 * 5)

    def _change_affection(self, delta):
        old_level = self._get_affection_level()
        self._affection = max(0, min(100, self._affection + delta))
        self.config["affection"] = self._affection
        save_config(self.config)

        if delta > 0:
            self.speak(random.choice(AFFECTION_UP_REPLIES))
        elif delta < 0:
            self.speak(random.choice(AFFECTION_DOWN_REPLIES))

        if old_level != self._get_affection_level() and self._control_panel:
            self._control_panel.refresh()

    def _touch_replies(self, zone):
        level = self._get_affection_level()
        if zone == "head":
            pool = {"low": PET_REPLIES_LOW, "mid": PET_REPLIES, "high": PET_REPLIES_HIGH}[level]
        elif zone == "body":
            pool = {"low": BODY_REPLIES_LOW, "mid": BODY_REPLIES, "high": BODY_REPLIES_HIGH}[level]
        else:
            pool = {"low": LEG_REPLIES_LOW, "mid": LEG_REPLIES, "high": LEG_REPLIES_HIGH}[level]
        return pool

    def _get_auto_line(self):
        return random.choice(LINES)

    # -------------------- 主动说话 --------------------

    def _get_auto_interval(self):
        return {0: 0, 1: 120000, 2: 60000, 3: 30000}.get(self._auto_talk_level, 60000)

    def _get_auto_chance(self):
        return {1: 0.35, 2: 0.2, 3: 0.14}.get(self._auto_talk_level, 0.2)

    def _rebuild_auto_talk(self):
        if self._auto_talk_timer:
            self._auto_talk_timer.stop()
        self._auto_talk_timer = None
        interval = self._get_auto_interval()
        if interval <= 0:
            return
        self._auto_talk_timer = QTimer(self)
        self._auto_talk_timer.setInterval(interval)
        self._auto_talk_timer.timeout.connect(self._check_auto_talk)
        self._auto_talk_timer.start()

    def _check_auto_talk(self):
        if (
            self._speaking
            or self._thinking_active
            or self.pomodoro.state in {"working", "paused", "break"}
        ):
            return
        if random.random() < self._get_auto_chance():
            self.speak(self._get_auto_line())

    def _set_auto_talk_level(self, level):
        self._auto_talk_level = max(0, min(3, level))
        self.config["auto_talk_level"] = self._auto_talk_level
        save_config(self.config)
        self._rebuild_auto_talk()

    # -------------------- 气泡和对话 --------------------

    def speak(self, text=None, save_to_history=False, touch_label="(触摸)", pose="waving"):
        if not text:
            text = random.choice(LINES)
            if save_to_history:
                save_session([
                    {"role": "user", "content": touch_label},
                    {"role": "assistant", "content": text},
                ])

        self.bubble.setText(text)
        self.bubble.adjustSize()
        self.bubble.move(
            max(10, (self.W - self.bubble.width()) // 2),
            22,
        )
        self.bubble.show()
        self._speaking = True
        self._set_pose(pose)
        self._bounce = -15
        self._hide_timer.start(3600)
        self.update()

    def _hide_bubble(self):
        self.bubble.hide()
        self._speaking = False
        if self._pending_waiting:
            reason, duration_ticks = self._pending_waiting
            self._pending_waiting = None
            self._start_waiting(reason, duration_ticks)
        elif self._click_gaze_pending:
            self._click_gaze_pending = False
            if not self._start_gaze(forced=True):
                self._sync_state_pose()
        else:
            self._sync_state_pose()

    def _show_chat_dialog(self):
        if self._chat_dialog and self._chat_dialog.isVisible():
            self._chat_dialog.raise_()
            self._chat_dialog.activateWindow()
            return
        self._chat_dialog = ChatDialog(self)
        self._chat_dialog.show()
        self._chat_dialog._position_near_pet()

    def _show_control_panel(self):
        if self._control_panel and self._control_panel.isVisible():
            self._control_panel.raise_()
            self._control_panel.activateWindow()
            return
        self._control_panel = ControlPanel(self)
        self._control_panel.show()
        self._control_panel._position_near_pet()

    # -------------------- 番茄钟 --------------------

    def _pomodoro_start(self):
        if self.pomodoro.state == "paused":
            self.pomodoro.resume()
            self.speak(f"专注继续～还剩 {self.pomodoro.format_time()}")
        else:
            self.pomodoro.start_work()
            self._set_pose("running")
            self.speak(f"专注 {self.pomodoro.work_minutes} 分钟开始。")
        if self._control_panel:
            self._control_panel.refresh()

    def _pomodoro_pause(self):
        if self.pomodoro.state == "working":
            self.pomodoro.pause()
            self._start_waiting("paused")
            self.speak(f"先暂停一下，还剩 {self.pomodoro.format_time()}。")
        if self._control_panel:
            self._control_panel.refresh()

    def _pomodoro_stop(self):
        if self.pomodoro.is_active or self.pomodoro.state == "paused":
            self.pomodoro.stop()
            self._set_pose("look")
            self.speak("番茄钟停好啦。")
        if self._control_panel:
            self._control_panel.refresh()

    def _pomodoro_set_duration(self):
        from PyQt5.QtWidgets import QInputDialog

        value, ok = QInputDialog.getInt(
            self,
            "番茄钟时长",
            "每次专注多少分钟？",
            self.pomodoro.work_minutes,
            5,
            60,
            5,
        )
        if ok:
            self.pomodoro.set_work_minutes(value)
            self.config["pomodoro_minutes"] = value
            save_config(self.config)
            self.speak(f"好啦，每个番茄 {value} 分钟。")
            if self._control_panel:
                self._control_panel.refresh()

    def _pomodoro_tick(self, remaining, state):
        self._sync_state_pose()
        self.update()
        if self._control_panel:
            self._control_panel.refresh()

    def _pomodoro_done(self, kind):
        self._set_pose("jumping")
        if kind == "work_done":
            self._change_affection(5)
            self._pending_waiting = ("break_intro", 30)
            self.speak(f"主人，{self.pomodoro.work_minutes} 分钟完成啦，起来休息一下吧。")
            self.pomodoro.start_break()
        else:
            self._change_affection(2)
            self.speak("休息结束啦，要不要再来一个番茄？")
        if self._control_panel:
            self._control_panel.refresh()

    # -------------------- 菜单和窗口 --------------------

    def _build_menu(self):
        self.menu = QMenu(self)
        self.menu.setStyleSheet(f"""
            QMenu {{
                background: #ffffff;
                border: 1px solid #ddddda;
                border-radius: 14px;
                padding: 7px;
                color: #171717;
                font-size: 12px;
            }}
            QMenu::item {{
                padding: 9px 28px 9px 14px;
                border-radius: 8px;
            }}
            QMenu::item:selected {{
                background: #eeeeeb;
            }}
            QMenu::separator {{
                height: 1px;
                background: #e7e7e3;
                margin: 5px 9px;
            }}
        """)

        def add(label, slot):
            action = QAction(label, self)
            action.triggered.connect(slot)
            self.menu.addAction(action)

        add("打开聊天", self._show_chat_dialog)
        add("番茄钟与状态", self._show_control_panel)
        add("API 配置", self._open_config)
        self.menu.addSeparator()
        add("切换窗口置顶", self._toggle_top)
        add("关闭小灰", self._close_pet)

    def _open_config(self):
        dialog = ModernConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.config = load_config()
            if self._chat_dialog:
                self._chat_dialog.config_refreshed()

    def _toggle_top(self):
        flags = self.windowFlags()
        if flags & Qt.WindowStaysOnTopHint:
            flags &= ~Qt.WindowStaysOnTopHint
        else:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _close_pet(self):
        self.speak("主人晚安～小灰先休息啦。")
        QTimer.singleShot(1100, QApplication.quit)

    def _place_initial(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.W - 28, screen.bottom() - self.H - 24)

    # -------------------- 动画与绘制 --------------------

    def _maybe_trigger_gaze(self):
        """空闲时以时间冷却 + 概率触发一次约 5 秒的视线动作。"""
        if self._speaking or self._dragging or self.pomodoro.state != "idle":
            return

        if self._pose == "look":
            self._gaze_ticks_left -= 1
            if self._gaze_ticks_left <= 0:
                self._gaze_cooldown = random.randint(105, 180)
                self._set_pose(self._gaze_return_pose)
            return

        if self._pose != "idle":
            return

        self._gaze_cooldown = max(0, self._gaze_cooldown - 1)
        # 每 0.8 秒抽一次签，避免每个 80ms 节拍都追踪鼠标。
        if self._gaze_cooldown == 0 and self._time % 10 == 0:
            if random.random() < 0.28:
                self._start_gaze()

    def _tick(self):
        self._time += 1

        if self._pose == "look" and self._gaze_ticks_left > 0 and not self._dragging:
            self._update_direction()

        if self._pose in self.frames:
            self._pose_ticks += 1
            if self._pose == "sleepy":
                # 犯困逐帧变慢：每帧停留约 1.28 秒，最后一帧保持不回环。
                if self._pose_ticks % 16 == 0:
                    self._frame = min(self._frame + 1, len(self.frames[self._pose]) - 1)
            elif self._pose_ticks % 2 == 0:
                self._frame = (self._frame + 1) % len(self.frames[self._pose])

        if self._pose in {"waiting", "sleepy"} and self._waiting_ticks_left > 0:
            self._waiting_ticks_left -= 1
            if self._waiting_ticks_left <= 0:
                self._clear_waiting()

        # 空闲时让 idle、短暂视线和犯困动作共同轮换，避免视线动画独占待机时间。
        if self._pose == "look" and self.pomodoro.state == "idle" and not self._speaking:
            self._maybe_trigger_gaze()
        elif self._pose == "idle" and self.pomodoro.state == "idle" and not self._speaking:
            self._idle_cycle_counter += 1
            self._maybe_trigger_gaze()
            if self._idle_cycle_counter >= 240:
                self._idle_cycle_counter = 0
                self._gaze_cooldown = random.randint(90, 150)
                self._start_waiting("sleepy", self.SLEEPY_DURATION_TICKS)

        if abs(self._bounce) > 0.4:
            self._bounce *= 0.86
        else:
            self._bounce = 0.0

        if self._pet_timer:
            self._pet_timer += 1
            self._pet_rot = math.sin(self._pet_timer * 0.55) * 4
            if self._pet_timer > 18:
                self._pet_timer = 0
                self._pet_rot = 0

        self.update()

    def _paint_status_rail(self, painter):
        # 状态条跟随 sprite 底部定位，保持约 30px 的呼吸距离。
        rail = QRect(24, self.sprite_rect.bottom() + 30, self.W - 48, 44)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 18))
        painter.drawRoundedRect(rail.translated(0, 3), 18, 18)
        painter.setPen(QColor(220, 220, 216, 235))
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.drawRoundedRect(rail, 18, 18)

        painter.setBrush(QColor("#171717" if self.pomodoro.state == "working" else "#8a8a84"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rail.x() + 13, rail.y() + 17, 10, 10)

        painter.setPen(QColor("#171717"))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        label = {
            "idle": "陪伴中",
            "working": "专注中",
            "paused": "已暂停",
            "break": "休息中",
        }.get(self.pomodoro.state, "陪伴中")
        painter.drawText(rail.x() + 29, rail.y() + 23, label)

        painter.setPen(QColor("#767676"))
        painter.setFont(QFont("Microsoft YaHei", 9))
        active_states = {"working", "paused", "break"}
        if self.pomodoro.state in active_states:
            detail = self.pomodoro.format_time()
        elif self._pose == "look":
            detail = f"视线 · {self.direction_label}"
        else:
            detail = "待机动画"
        painter.drawText(
            QRect(rail.x() + 86, rail.y(), 88, rail.height()),
            Qt.AlignRight | Qt.AlignVCenter,
            detail,
        )

        painter.setPen(QColor("#171717"))
        painter.drawText(
            QRect(rail.right() - 64, rail.y(), 56, rail.height()),
            Qt.AlignRight | Qt.AlignVCenter,
            f"♥ {self._affection}",
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 地面柔光
        glow = QRadialGradient(self.W / 2, 290, 100)
        glow.setColorAt(0, QColor(0, 0, 0, 24))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(42, 255, self.W - 84, 95)

        # 小灰本体
        offset_y = math.sin(self._time * 0.055) * 3 + self._bounce
        pixmap = self._current_pixmap()
        draw_rect = QRect(
            self.sprite_rect.x(),
            self.sprite_rect.y() + int(offset_y),
            self.sprite_rect.width(),
            self.sprite_rect.height(),
        )

        if self._pet_rot:
            painter.save()
            center = draw_rect.center()
            painter.translate(center)
            painter.rotate(self._pet_rot)
            painter.translate(-center)
            painter.drawPixmap(draw_rect, pixmap)
            painter.restore()
        else:
            painter.drawPixmap(draw_rect, pixmap)

        self._paint_status_rail(painter)

    # -------------------- 交互 --------------------

    def _touch_zone(self, pos):
        rel = pos.y() - self.sprite_rect.top()
        ratio = rel / max(1, self.sprite_rect.height())
        if ratio < 0.48:
            return "head"
        if ratio < 0.76:
            return "body"
        return "leg"

    def _register_click_interaction(self):
        """只有真实点击才打断犯困计时；鼠标移动/look 不调用此方法。"""
        self._idle_cycle_counter = 0
        if self._waiting_reason == "sleepy":
            self._waiting_reason = None
            self._waiting_ticks_left = 0
            self._set_pose("idle")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._register_click_interaction()
            self.menu.exec_(event.globalPos())
            return
        if event.button() == Qt.LeftButton:
            self._register_click_interaction()
            self._dragging = True
            self._drag_direction = self._direction
            self._press_pos = event.globalPos()
            self._drag_last_pos = event.globalPos()
            self._drag_pose = None
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            current_pos = event.globalPos()
            delta = current_pos - self._drag_last_pos
            self.move(current_pos - self._drag_offset)
            if delta.manhattanLength() > 1:
                total_dx = current_pos.x() - self._press_pos.x()
                if abs(delta.x()) >= 2:
                    self._drag_pose = "running-right" if delta.x() > 0 else "running-left"
                elif self._drag_pose is None:
                    self._drag_pose = "running-right" if total_dx >= 0 else "running-left"
                if self._pose != self._drag_pose:
                    self._set_pose(self._drag_pose)
                self._drag_last_pos = current_pos
        else:
            self._update_direction()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        moved = (event.globalPos() - self._press_pos).manhattanLength() > 7
        self._dragging = False
        if moved:
            self._drag_pose = None
            self._sync_state_pose()
            return

        zone = self._touch_zone(event.pos())
        self._pet_timer = 1
        if self.pomodoro.state == "working":
            reply = random.choice(POMO_REPLIES).replace("{time}", self.pomodoro.format_time())
        else:
            reply = random.choice(self._touch_replies(zone))
        self._change_affection(1 if zone == "head" else 0)
        # 点击链路固定为：挥手 → 约 5 秒视线；不再依赖随机概率。
        self._click_gaze_pending = True
        self.speak(reply, save_to_history=True, touch_label=f"(摸{zone})")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_chat_dialog()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._close_pet()


class BaseDialog(QDialog):
    def __init__(self, parent=None, width=430, height=560):
        super().__init__(parent)
        self.parent_pet = parent
        self.setWindowTitle("小灰")
        self.setFixedSize(width, height)
        self.setStyleSheet(app_stylesheet())
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 38))
        self.setGraphicsEffect(shadow)

    def _position_near_pet(self):
        if not self.parent_pet:
            return
        parent_geo = self.parent_pet.geometry()
        screen = QApplication.primaryScreen().availableGeometry()
        x = parent_geo.left() - self.width() - 18
        if x < screen.left():
            x = parent_geo.right() + 18
        y = max(screen.top() + 18, min(parent_geo.top(), screen.bottom() - self.height() - 18))
        self.move(x, y)

    def _close_button(self, layout):
        button = QPushButton("关闭")
        button.setObjectName("quiet")
        button.clicked.connect(self.close)
        layout.addWidget(button)
        return button


class ModernHistoryDialog(BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, 520, 600)
        self.sessions = []
        self._build_ui()
        self._load_sessions()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        eyebrow = QLabel("XIAOHUI  /  MEMORY")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("聊天记录")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("保留每一次认真说过的话。")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        self.session_list = QListWidget()
        self.session_list.currentRowChanged.connect(self._show_detail)
        layout.addWidget(self.session_list, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(170)
        layout.addWidget(self.detail)

        buttons = QHBoxLayout()
        clear = QPushButton("清空记录")
        clear.setObjectName("quiet")
        clear.clicked.connect(self._clear_history)
        buttons.addWidget(clear)
        buttons.addStretch()
        close = QPushButton("关闭")
        close.setObjectName("accent")
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _load_sessions(self):
        self.sessions = list(reversed(load_history()))
        self.session_list.clear()
        for session in self.sessions:
            item = QListWidgetItem(f"{session.get('time', '')}   {session.get('preview', '')}")
            self.session_list.addItem(item)
        if self.session_list.count():
            self.session_list.setCurrentRow(0)

    def _show_detail(self, index):
        if index < 0 or index >= len(self.sessions):
            self.detail.clear()
            return
        messages = self.sessions[index].get("messages", [])
        self.detail.setPlainText(
            "\n\n".join(
                ("你：" if message.get("role") == "user" else "小灰：")
                + message.get("content", "")
                for message in messages
            )
        )

    def _clear_history(self):
        from chat import HISTORY_FILE
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            file.write("[]")
        self._load_sessions()
        self.detail.clear()


class ModernConfigDialog(BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, 500, 380)
        self.config = load_config()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        eyebrow = QLabel("XIAOHUI  /  CONNECTION")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("连接设置")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("密钥只保存在本机配置文件中。")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("API Key"), 0, 0)
        self.key_edit = QLineEdit(self.config.get("deepseek_api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.Password)
        grid.addWidget(self.key_edit, 0, 1)

        grid.addWidget(QLabel("模型"), 1, 0)
        self.model_edit = QLineEdit(self.config.get("deepseek_model", "deepseek-chat"))
        grid.addWidget(self.model_edit, 1, 1)

        grid.addWidget(QLabel("地址"), 2, 0)
        self.url_edit = QLineEdit(self.config.get("deepseek_base_url", ""))
        grid.addWidget(self.url_edit, 2, 1)
        layout.addWidget(card)

        buttons = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.setObjectName("quiet")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        buttons.addStretch()
        save = QPushButton("保存设置")
        save.setObjectName("accent")
        save.clicked.connect(self.accept)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def accept(self):
        self.config["deepseek_api_key"] = self.key_edit.text().strip()
        self.config["deepseek_model"] = self.model_edit.text().strip()
        self.config["deepseek_base_url"] = self.url_edit.text().strip()
        save_config(self.config)
        super().accept()



class ChatDialog(BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, 470, 620)
        self.messages = []
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        eyebrow = QLabel("XIAOHUI  /  COMPANION")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        title_row = QHBoxLayout()
        title = QLabel("和小灰聊聊")
        title.setObjectName("title")
        title_row.addWidget(title)
        title_row.addStretch()
        history = QPushButton("历史")
        history.setObjectName("quiet")
        history.clicked.connect(self._show_history)
        title_row.addWidget(history)
        config = QPushButton("设置")
        config.setObjectName("quiet")
        config.clicked.connect(self._config)
        title_row.addWidget(config)
        layout.addLayout(title_row)

        subtitle = QLabel("把想法交给我，我会安静地陪着你。")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        self.view = QListWidget()
        self.view.setSpacing(8)
        self.view.setSelectionMode(QListWidget.NoSelection)
        self.view.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.view, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入一句话，回车发送……")
        self.input.returnPressed.connect(self._send)
        input_row.addWidget(self.input, 1)
        send = QPushButton("发送")
        send.setObjectName("accent")
        send.setMinimumWidth(70)
        send.clicked.connect(self._send)
        input_row.addWidget(send)
        layout.addLayout(input_row)

        close = QPushButton("收起聊天")
        close.setObjectName("quiet")
        close.clicked.connect(self.close)
        layout.addWidget(close)

        self._append_message("小灰", "我在这里，主人想聊什么？", False)

    def _append_message(self, who, text, user):
        item = QListWidgetItem()
        item.setSizeHint(item.sizeHint())
        item.setText(f"{'你' if user else '小灰'}  ·  {text}")
        if user:
            item.setForeground(QColor("#555555"))
        else:
            item.setForeground(QColor("#171717"))
        self.view.addItem(item)
        self.view.scrollToBottom()

    def _send(self):
        text = self.input.text().strip()
        if not text or self.worker:
            return

        config = self.parent_pet.config
        if not config.get("deepseek_api_key"):
            self._append_message("小灰", "还没有 API 密钥，请先打开设置配置。", False)
            return

        self.input.clear()
        self.input.setEnabled(False)
        self.messages.append({"role": "user", "content": text})
        self._append_message("你", text, True)

        system_prompt = get_affection_system_prompt(self.parent_pet._get_affection_level())
        payload = [{"role": "system", "content": system_prompt}] + self.messages[-10:]
        self.worker = DeepSeekWorker(
            config.get("deepseek_api_key", ""),
            config.get("deepseek_base_url", ""),
            config.get("deepseek_model", "deepseek-chat"),
            payload,
            temperature=0.85,
        )
        self.parent_pet._thinking_active = True
        self.parent_pet._start_waiting("thinking")
        self.parent_pet.speak("我想想……", pose="waiting")
        self.worker.finished.connect(self._on_response)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_response(self, content):
        self.worker = None
        self.parent_pet._thinking_active = False
        content = content.strip()
        if content.startswith("[INSULT]"):
            content = content.replace("[INSULT]", "", 1).strip()
            self.parent_pet._change_affection(-5)
        else:
            self.parent_pet._change_affection(1)
        self.messages.append({"role": "assistant", "content": content})
        self._append_message("小灰", content, False)
        self.parent_pet.speak(content)
        save_session(self.messages)
        self.input.setEnabled(True)
        self.input.setFocus()

    def _on_error(self, error_msg):
        self.worker = None
        self.parent_pet._thinking_active = False
        self._append_message("小灰", f"连接失败：{error_msg[:60]}", False)
        self.input.setEnabled(True)
        self.input.setFocus()
        self.parent_pet.speak("刚才的连接有点不稳，再试一次吧。")

    def _show_history(self):
        ModernHistoryDialog(self).exec_()

    def _config(self):
        self.parent_pet._open_config()

    def config_refreshed(self):
        self.parent_pet.config = load_config()

    def closeEvent(self, event):
        self.parent_pet._chat_dialog = None
        super().closeEvent(event)


class ControlPanel(BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, 480, 680)
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(1000)

    def _card(self):
        card = QFrame()
        card.setObjectName("card")
        return card

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        heading = QVBoxLayout()
        heading.setSpacing(3)
        eyebrow = QLabel("XIAOHUI  /  CONTROL")
        eyebrow.setObjectName("eyebrow")
        heading.addWidget(eyebrow)
        title = QLabel("陪伴控制台")
        title.setObjectName("title")
        heading.addWidget(title)
        subtitle = QLabel("管理专注节奏，也看看小灰现在的状态。")
        subtitle.setObjectName("subtitle")
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        close_top = QPushButton("×")
        close_top.setObjectName("quiet")
        close_top.setFixedSize(32, 32)
        close_top.setStyleSheet("font-size:20px;padding:0;border-radius:16px;")
        close_top.clicked.connect(self.close)
        header.addWidget(close_top, 0, Qt.AlignTop)
        layout.addLayout(header)

        self.status_card = self._card()
        self.status_card.setObjectName("statusCard")
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(18, 14, 18, 14)
        status_row = QHBoxLayout()
        status_copy = QVBoxLayout()
        status_copy.setSpacing(4)
        self.status_title = QLabel()
        self.status_title.setStyleSheet("font-size:17px;font-weight:700;color:#171717;")
        status_copy.addWidget(self.status_title)
        self.status_detail = QLabel()
        self.status_detail.setObjectName("subtitle")
        status_copy.addWidget(self.status_detail)
        status_row.addLayout(status_copy, 1)
        self.status_timer = QLabel()
        self.status_timer.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_timer.setStyleSheet("font-size:22px;font-weight:700;color:#171717;")
        status_row.addWidget(self.status_timer)
        status_layout.addLayout(status_row)
        layout.addWidget(self.status_card)

        timer_card = self._card()
        timer_layout = QVBoxLayout(timer_card)
        timer_layout.setContentsMargins(18, 14, 18, 14)
        timer_header = QHBoxLayout()
        section = QLabel("专注计时")
        section.setObjectName("section")
        timer_header.addWidget(section)
        timer_header.addStretch()
        self.timer_hint = QLabel()
        self.timer_hint.setObjectName("subtitle")
        timer_header.addWidget(self.timer_hint)
        timer_layout.addLayout(timer_header)

        self.timer_clock = QLabel()
        self.timer_clock.setAlignment(Qt.AlignCenter)
        self.timer_clock.setStyleSheet("font-size:27px;font-weight:700;color:#171717;padding:2px 0 5px;")
        timer_layout.addWidget(self.timer_clock)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        for text, slot, name in (
            ("开始", self.parent_pet._pomodoro_start, "accent"),
            ("暂停", self.parent_pet._pomodoro_pause, "quiet"),
            ("停止", self.parent_pet._pomodoro_stop, "quiet"),
        ):
            button = QPushButton(text)
            button.setObjectName(name)
            button.setMinimumHeight(34)
            button.clicked.connect(slot)
            button_row.addWidget(button)
        timer_layout.addLayout(button_row)

        duration = QPushButton("调整专注时长")
        duration.setObjectName("quiet")
        duration.setMinimumHeight(30)
        duration.clicked.connect(self.parent_pet._pomodoro_set_duration)
        timer_layout.addWidget(duration)
        layout.addWidget(timer_card)

        affection_card = self._card()
        affection_layout = QVBoxLayout(affection_card)
        affection_layout.setContentsMargins(18, 14, 18, 14)
        affection_header = QHBoxLayout()
        affection_title = QLabel("和小灰的连接")
        affection_title.setObjectName("section")
        affection_header.addWidget(affection_title)
        affection_header.addStretch()
        self.affection_label = QLabel()
        self.affection_label.setStyleSheet("font-size:15px;font-weight:700;color:#171717;")
        affection_header.addWidget(self.affection_label)
        affection_layout.addLayout(affection_header)
        self.affection_bar = QProgressBar()
        self.affection_bar.setTextVisible(False)
        affection_layout.addWidget(self.affection_bar)
        layout.addWidget(affection_card)

        auto_card = self._card()
        auto_layout = QVBoxLayout(auto_card)
        auto_layout.setContentsMargins(18, 14, 18, 14)
        auto_header = QHBoxLayout()
        auto_label = QLabel("主动陪伴频率")
        auto_label.setObjectName("section")
        auto_header.addWidget(auto_label)
        auto_header.addStretch()
        self.auto_value = QLabel()
        self.auto_value.setObjectName("subtitle")
        auto_header.addWidget(self.auto_value)
        auto_layout.addLayout(auto_header)
        levels = QHBoxLayout()
        levels.setSpacing(8)
        self.auto_buttons = []
        for index, text in enumerate(("关闭", "低", "中", "高")):
            button = QPushButton(text)
            button.setMinimumHeight(32)
            button.clicked.connect(lambda checked=False, value=index: self._set_auto_level(value))
            levels.addWidget(button)
            self.auto_buttons.append(button)
        auto_layout.addLayout(levels)
        layout.addWidget(auto_card)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        api = QPushButton("API 设置")
        api.setObjectName("quiet")
        api.setMinimumHeight(36)
        api.clicked.connect(self.parent_pet._open_config)
        actions.addWidget(api)
        top = QPushButton("切换置顶")
        top.setObjectName("quiet")
        top.setMinimumHeight(36)
        top.clicked.connect(self.parent_pet._toggle_top)
        actions.addWidget(top)
        layout.addLayout(actions)

        close_bottom = QPushButton("完成，收起控制台")
        close_bottom.setObjectName("accent")
        close_bottom.setMinimumHeight(38)
        close_bottom.clicked.connect(self.close)
        layout.addWidget(close_bottom)

        self.refresh()

    def _set_auto_level(self, level):
        self.parent_pet._set_auto_talk_level(level)
        self.refresh()

    def refresh(self):
        state = self.parent_pet.pomodoro.state
        labels = {
            "idle": ("陪伴中", "小灰正在待机，视线动作会偶尔触发。", "待机"),
            "working": ("专注中", "保持节奏，专注倒计时进行中。", self.parent_pet.pomodoro.format_time()),
            "paused": ("已暂停", "计时已暂停，可以继续或停止。", self.parent_pet.pomodoro.format_time()),
            "break": ("休息中", "放松一下，休息倒计时进行中。", self.parent_pet.pomodoro.format_time()),
        }
        title, detail, clock = labels.get(state, labels["idle"])
        self.status_title.setText(title)
        self.status_detail.setText(detail)
        self.status_timer.setText(clock)
        if state == "working":
            self.timer_hint.setText("进行中")
            self.timer_clock.setText(self.parent_pet.pomodoro.format_time())
        elif state == "paused":
            self.timer_hint.setText("已暂停")
            self.timer_clock.setText(self.parent_pet.pomodoro.format_time())
        elif state == "break":
            self.timer_hint.setText("休息阶段")
            self.timer_clock.setText(self.parent_pet.pomodoro.format_time())
        else:
            self.timer_hint.setText("尚未开始")
            self.timer_clock.setText("--:--")
        self.affection_label.setText(f"好感度  {self.parent_pet._affection} / 100")
        self.affection_bar.setValue(self.parent_pet._affection)
        names = ("关闭", "低", "中", "高")
        current_level = max(0, min(3, self.parent_pet._auto_talk_level))
        self.auto_value.setText(f"当前：{names[current_level]}")
        for index, button in enumerate(self.auto_buttons):
            button.setObjectName("accent" if index == current_level else "quiet")
            button.style().unpolish(button)
            button.style().polish(button)

    def closeEvent(self, event):
        self.parent_pet._control_panel = None
        self._refresh_timer.stop()
        super().closeEvent(event)
