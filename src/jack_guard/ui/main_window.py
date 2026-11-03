from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jack_guard.ui.strings import tr

STYLE = """
QWidget { background: #111827; color: #e5edf8; font-family: 'Segoe UI'; font-size:14px; }
QLabel#title { font-size:32px; font-weight:700; color:#64dfbd; }
QLabel#muted { color:#9caec6; }
QPushButton { background:#26364d; border:1px solid #41536d; border-radius:7px;
              padding:12px 18px; }
QPushButton:hover { background:#354c69; }
QPushButton#primary { background:#176957; border:1px solid #47b69e; font-size:18px; }
QTextEdit, QLineEdit, QListWidget, QSpinBox { background:#1b2638; border:1px solid #41536d;
                                          padding:8px; selection-background-color:#176957; }
QTabBar::tab { padding:10px; background:#26364d; }
QTabBar::tab:selected { background:#176957; }
QCheckBox { padding:5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = None
        self.setWindowTitle("JACK GUARD")
        self.resize(820, 610)
        center = QWidget()
        self.setCentralWidget(center)
        box = QVBoxLayout(center)
        box.setContentsMargins(28, 24, 28, 24)
        title = QLabel("JACK GUARD")
        title.setObjectName("title")
        box.addWidget(title)
        subtitle = QLabel("나의 화면, 나의 시간 · 로컬 프라이버시 도우미")
        subtitle.setObjectName("muted")
        box.addWidget(subtitle)
        self.status = QLabel()
        box.addWidget(self.status)
        hint = QLabel(
            "실제 접근 차단은 Windows 잠금을 사용하세요.\n"
            "프라이버시 모드는 창 숨김 또는 화면 가림이며, OS를 잠그지 않습니다."
        )
        hint.setObjectName("muted")
        box.addWidget(hint)
        row = QHBoxLayout()
        self.lock_button = QPushButton(tr("lock"))
        self.lock_button.setObjectName("primary")
        self.privacy_button = QPushButton(tr("privacy"))
        row.addWidget(self.lock_button)
        row.addWidget(self.privacy_button)
        box.addLayout(row)
        self.hotkey_label = QLabel()
        self.hotkey_label.setObjectName("muted")
        box.addWidget(self.hotkey_label)
        box.addWidget(QLabel("최근 이벤트 · UTC"))
        self.recent = QTextEdit()
        self.recent.setReadOnly(True)
        box.addWidget(self.recent)
        footer = QHBoxLayout()
        self.settings_button = QPushButton(tr("settings"))
        self.pause_button = QPushButton("감지 일시 중지 / 재개")
        self.quit_button = QPushButton(tr("quit"))
        footer.addWidget(self.settings_button)
        footer.addWidget(self.pause_button)
        footer.addStretch()
        footer.addWidget(self.quit_button)
        box.addLayout(footer)

    def closeEvent(self, event):
        if (
            self.controller
            and self.controller.tray.isVisible()
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            self.hide()
            event.ignore()
        else:
            event.accept()
