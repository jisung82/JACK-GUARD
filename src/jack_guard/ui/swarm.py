"""Original, app-local reconstruction effect. No OS cursor movement or input blocking."""

import ctypes
import math
import sys
import time

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QPushButton, QWidget

from jack_guard.ui.design import ACCENT, BG, BORDER, MUTED, TEXT, terminal_font


def system_reduced_motion():
    if sys.platform != "win32":
        return False
    enabled = ctypes.c_int(0)
    api = ctypes.WinDLL("user32", use_last_error=True).SystemParametersInfoW
    if not api(0x1042, 0, ctypes.byref(enabled), 0):
        return True  # Unknown policy: prefer the static interface.
    return not bool(enabled.value)


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


class SwarmOverlay(QWidget):
    completed = Signal(dict)
    emergency_lock = Signal()

    def __init__(self, window):
        super().__init__(window.center)
        self.window = window
        self.active = False
        self.snapshot = None
        self.regions = []
        self.intervals = []
        self.paint_count = 0
        self.recapture_pending = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Swarm 인트로. 아무 키나 클릭으로 건너뛰기")
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.lock_button = QPushButton("LOCK NOW  /  Ctrl+Shift+L", self)
        self.lock_button.clicked.connect(self.emergency)
        self.parent().installEventFilter(self)
        self.hide()

    def capture(self):
        self.recapture_pending = False
        if not self.active:
            return
        self.hide()
        self.setGeometry(self.parent().rect())
        self.snapshot = self.parent().grab()
        self.regions = [
            QRectF(w.mapTo(self.parent(), QPoint(0, 0)), w.size())
            for w in self.window.reveal_regions()
        ]
        self.lock_button.setGeometry(max(8, self.width() - 286), 8, 276, 34)
        self.show()
        self.raise_()
        self.setFocus()

    def start(self, speed=1, cursors=5, automatic=True):
        if self.active:
            self.finish("restarted")
        self.speed, self.cursors, self.automatic = speed, cursors, automatic
        self.active = True
        self.elapsed = 0.0
        self.intervals = []
        self.paint_count = 0
        self.started = self.previous = time.perf_counter()
        self.capture()
        self.timer.start()

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() == QEvent.Type.Resize and self.active:
            self.setGeometry(self.parent().rect())
            if not self.recapture_pending:
                self.recapture_pending = True
                QTimer.singleShot(0, self.capture)
        return False

    def tick(self):
        now = time.perf_counter()
        self.intervals.append((now - self.previous) * 1000)
        self.previous = now
        self.elapsed = (now - self.started) * self.speed
        if self.automatic and len(self.intervals) >= 8 and (sum(self.intervals[-8:]) / 8 > 24):
            self.finish("reduced-frame-rate")
        elif self.elapsed >= 2.8:
            self.finish("complete")
        else:
            self.update()

    def finish(self, reason="skipped"):
        if not self.active:
            return
        elapsed = time.perf_counter() - self.started
        self.active = False
        self.timer.stop()
        self.hide()
        self.snapshot = None
        self.window.command.setFocus()
        self.completed.emit(
            {
                "reason": reason,
                "duration_ms": round(elapsed * 1000, 2),
                "paints": self.paint_count,
                "paint_fps": round(self.paint_count / elapsed, 2) if elapsed else 0,
                "max_frame_ms": round(max(self.intervals, default=0), 2),
                "timer_active_after": self.timer.isActive(),
            }
        )

    def emergency(self):
        self.finish("emergency-lock")
        self.emergency_lock.emit()

    def mousePressEvent(self, event):
        self.finish("mouse-skip")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_L and event.modifiers() == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            self.emergency()
        else:
            self.finish("keyboard-skip")

    def paintEvent(self, event):
        if not self.active or self.snapshot is None:
            return
        self.paint_count += 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG))
        t = self.elapsed
        starts = [0.15, 0.65, 1.05, 1.35, 1.75, 2.15]
        if t >= 2.55:
            painter.drawPixmap(0, 0, self.snapshot)
        else:
            for index, rect in enumerate(self.regions):
                progress = max(0.0, min(1.0, (t - starts[index]) / 0.48))
                if not progress:
                    continue
                painter.save()
                # Reveal the real widget pixels row by row; no simulated status/log content.
                rows = max(1, math.ceil(rect.height() / 19))
                position = progress * rows
                complete = int(position)
                self.draw_region(
                    painter,
                    QRectF(rect.x(), rect.y(), rect.width(), min(rect.height(), complete * 19)),
                )
                if complete < rows:
                    self.draw_region(
                        painter,
                        QRectF(
                            rect.x(),
                            rect.y() + complete * 19,
                            rect.width() * (position - complete),
                            min(19, rect.height() - complete * 19),
                        ),
                    )
                painter.restore()
                painter.setPen(QPen(QColor(BORDER), 1))
                painter.drawLine(
                    rect.topLeft(), QPointF(rect.left() + rect.width() * ease(progress), rect.top())
                )
        if 0.3 <= t < 2.8:
            for i in range(self.cursors):
                tasks = [j for j in range(len(self.regions)) if j % self.cursors == i]
                if not tasks:
                    tasks = [i % len(self.regions)]
                task = max((j for j in tasks if t >= starts[j] - 0.3), default=tasks[0])
                rect = self.regions[task]
                start = starts[task]
                approach = ease((t - max(0.3, start - 0.3)) / 0.35)
                work = max(0.0, min(1.0, (t - start) / 0.48))
                target = QPointF(
                    rect.left() + min(rect.width() - 8, rect.width() * work),
                    rect.top() + min(rect.height() - 8, work * rect.height()),
                )
                origin = QPointF(self.width() / 2 + (i - 2) * 18, self.height() / 2)
                if task != tasks[0]:
                    previous = self.regions[tasks[tasks.index(task) - 1]]
                    origin = QPointF(previous.right() - 8, previous.bottom() - 8)
                point = origin * (1 - approach) + target * approach
                point.setY(point.y() + math.sin(approach * math.pi) * (24 + i * 3))
                if t > 2.6:
                    depart = ease((t - 2.6) / 0.2)
                    point = point * (1 - depart) + QPointF(self.width() + 20, -20) * depart
                painter.save()
                painter.translate(point)
                painter.setPen(QPen(QColor(BG), 1))
                painter.setBrush(QColor(ACCENT if i == 0 else TEXT))
                painter.drawPolygon(
                    QPolygonF(
                        [
                            QPointF(0, 0),
                            QPointF(0, 13),
                            QPointF(4, 9),
                            QPointF(8, 16),
                            QPointF(11, 14),
                            QPointF(7, 7),
                            QPointF(13, 7),
                        ]
                    )
                )
                painter.restore()
        painter.setPen(QColor(MUTED))
        painter.setFont(terminal_font(9))
        painter.drawText(28, self.height() - 14, "REBUILD / any key or click to skip")
        painter.end()

    def draw_region(self, painter, rect):
        if rect.width() <= 0 or rect.height() <= 0:
            return
        ratio = self.snapshot.devicePixelRatioF()
        source = QRectF(
            rect.x() * ratio, rect.y() * ratio, rect.width() * ratio, rect.height() * ratio
        )
        painter.drawPixmap(rect, self.snapshot, source)
