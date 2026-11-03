from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class Privacy:
    def __init__(self, window, event):
        self.window, self.event = window, event
        self.active = False
        self.covers = []
        self.dialog = None

    def enter(self, overlay=False):
        if self.active:
            self.leave()
            return
        if self.dialog:
            self.dialog.reject()
        self.window.hide()
        self.active = True
        if overlay:
            for screen in QApplication.screens():
                cover = QWidget()
                cover.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                )
                cover.setStyleSheet("background:#101722;color:#edf3fb;font-size:22px;")
                layout = QVBoxLayout(cover)
                layout.addStretch()
                label = QLabel("JACK GUARD\n\n화면 가림 · Windows가 잠겨 있지 않습니다.")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)
                button = QPushButton("화면 가림 해제 / Restore")
                button.clicked.connect(self.leave)
                layout.addWidget(button)
                layout.addStretch()
                cover.setGeometry(screen.geometry())
                cover.show()
                self.covers.append(cover)
        self.event("프라이버시 시작", "화면 가림" if overlay else "창 숨김")

    def leave(self):
        for cover in self.covers:
            cover.close()
            cover.deleteLater()
        self.covers.clear()
        if self.active:
            self.event("프라이버시 종료")
        self.active = False
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
