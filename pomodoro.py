# -*- coding: utf-8 -*-
"""
星绊桌宠 — 番茄钟模块
"""

from PyQt5.QtCore import QTimer


class PomodoroTimer:
    """番茄钟：可调时长工作 / 5分钟休息"""

    BREAK_MINUTES = 5

    def __init__(self, on_tick=None, on_done=None, work_minutes=25):
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self.on_tick = on_tick    # 每秒回调(remaining_seconds, state_text)
        self.on_done = on_done    # 完成回调(state_text)

        self._work_minutes = work_minutes
        self.reset()

    @property
    def work_minutes(self):
        return self._work_minutes

    def set_work_minutes(self, minutes):
        """设置工作时长（仅空闲时可修改）"""
        if self.state == "idle":
            self._work_minutes = max(5, min(60, minutes))
            self.remaining = self._work_minutes * 60

    def reset(self):
        """重置到空闲状态"""
        self._timer.stop()
        self.state = "idle"       # idle / working / paused / break
        self.remaining = self._work_minutes * 60

    @property
    def is_active(self):
        return self.state in ("working", "break")

    def start_work(self):
        """开始工作番茄"""
        if self.state == "paused":
            self._timer.start()
            self.state = "working"
            return
        self.state = "working"
        self.remaining = self._work_minutes * 60
        self._timer.start()
        self._notify_tick()

    def start_break(self):
        """开始休息"""
        self.state = "break"
        self.remaining = self.BREAK_MINUTES * 60
        self._timer.start()
        self._notify_tick()

    def pause(self):
        """暂停"""
        if self.state == "working":
            self.state = "paused"
            self._timer.stop()
            self._notify_tick()

    def resume(self):
        """继续"""
        if self.state == "paused":
            self.state = "working"
            self._timer.start()
            self._notify_tick()

    def stop(self):
        """停止"""
        self.reset()
        self._notify_tick()

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self._timer.stop()
            if self.state == "working":
                self.state = "idle"
                self.remaining = self._work_minutes * 60
                self._notify_done("work_done")
            elif self.state == "break":
                self.state = "idle"
                self.remaining = self._work_minutes * 60
                self._notify_done("break_done")
            return
        self._notify_tick()

    def _notify_tick(self):
        if self.on_tick:
            self.on_tick(self.remaining, self.state)

    def _notify_done(self, kind):
        if self.on_done:
            self.on_done(kind)

    def format_time(self, seconds=None):
        """返回 MM:SS 格式字符串"""
        s = seconds if seconds is not None else self.remaining
        m = s // 60
        sec = s % 60
        return f"{m:02d}:{sec:02d}"

    def state_label(self):
        return {
            "idle": "空闲",
            "working": "专注中",
            "paused": "已暂停",
            "break": "休息中",
        }.get(self.state, "空闲")
