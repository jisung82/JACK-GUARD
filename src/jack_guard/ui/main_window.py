from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from jack_guard import __version__
from jack_guard.ui.terminal import CommandLine


def rule():
    line = QFrame()
    line.setObjectName("rule")
    return line


def section(text):
    label = QLabel(text)
    label.setObjectName("section")
    return label


class MainWindow(QMainWindow):
    command_requested = Signal(str)
    replay_requested = Signal()

    def __init__(self):
        super().__init__()
        self.controller = None
        self.terminal_colors = None
        self.intro = None
        self.setWindowTitle("JACK GUARD — TERMINAL EDITION")
        self.resize(1100, 700)
        self.setMinimumSize(850, 550)
        self.center = QWidget()
        self.setCentralWidget(self.center)
        root = QVBoxLayout(self.center)
        root.setContentsMargins(28, 22, 28, 12)
        root.setSpacing(14)
        self.header = QWidget()
        top = QHBoxLayout(self.header)
        top.setContentsMargins(0, 0, 0, 0)
        branding = QVBoxLayout()
        title = QLabel("JACK GUARD / TERMINAL EDITION")
        title.setObjectName("brand")
        branding.addWidget(title)
        subtitle = QLabel("Personal privacy control system")
        subtitle.setObjectName("muted")
        branding.addWidget(subtitle)
        top.addLayout(branding)
        top.addStretch()
        build = section(f"v{__version__}\nLOCAL / CURRENT USER")
        build.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(build)
        root.addWidget(self.header)
        root.addWidget(rule())
        body = QHBoxLayout()
        body.setSpacing(28)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(8)
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.state_panel = QWidget()
        self.state_panel.setFixedWidth(260)
        self.state_panel.setMinimumHeight(132)
        states = QVBoxLayout(self.state_panel)
        states.setContentsMargins(0, 0, 0, 0)
        states.setSpacing(11)
        states.addWidget(section("SYSTEM STATUS"))
        self.states = {}
        for key in ("SESSION", "PRIVACY", "MONITOR", "HOTKEY"):
            row = QHBoxLayout()
            name = section(key)
            name.setFixedWidth(90)
            value = QLabel("—")
            value.setObjectName("value")
            row.addWidget(name)
            row.addWidget(value)
            states.addLayout(row)
            self.states[key] = value
        sidebar.addWidget(self.state_panel)
        sidebar.addWidget(rule())
        self.navigation = QWidget()
        nav = QVBoxLayout(self.navigation)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(3)
        entries = [
            ("lock_button", "[01] LOCK WORKSTATION", "lock"),
            ("privacy_button", "[02] ENABLE PRIVACY", "privacy on"),
            ("monitor_button", "[03] PROCESS MONITOR", "monitor status"),
            ("logs_button", "[04] EVENT LOG", "logs"),
            ("settings_button", "[05] SETTINGS", "settings"),
        ]
        for attr, text, command in entries:
            button = QPushButton(text)
            button.setObjectName("nav")
            button.setMinimumHeight(38)
            button.setToolTip(command)
            button.clicked.connect(lambda checked=False, c=command: self.command_requested.emit(c))
            nav.addWidget(button)
            setattr(self, attr, button)
        sidebar.addWidget(self.navigation)
        self.pause_button = QPushButton("MONITOR  /  START・PAUSE")
        sidebar.addWidget(self.pause_button)
        self.replay_button = QPushButton("REPLAY INTRO  ↗")
        self.replay_button.clicked.connect(self.replay_requested)
        sidebar.addWidget(self.replay_button)
        sidebar.addStretch()
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.status.setFixedWidth(260)
        sidebar.addWidget(self.status)
        self.hotkey_label = QLabel()
        self.hotkey_label.setObjectName("muted")
        self.hotkey_label.setWordWrap(True)
        self.hotkey_label.setFixedWidth(260)
        sidebar.addWidget(self.hotkey_label)
        sidebar_content = QWidget()
        sidebar_content.setLayout(sidebar)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidget(sidebar_content)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFixedWidth(272)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.addWidget(sidebar_scroll)
        workspace = QSplitter(Qt.Orientation.Vertical)
        self.console_panel = QWidget()
        console_layout = QVBoxLayout(self.console_panel)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(8)
        console_layout.addWidget(section("CONTROL SHELL  /  BUILT-IN COMMANDS"))
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(600)
        self.console.setAccessibleName("명령 실행 결과")
        console_layout.addWidget(self.console)
        workspace.addWidget(self.console_panel)
        self.events_panel = QWidget()
        event_layout = QVBoxLayout(self.events_panel)
        event_layout.setContentsMargins(0, 0, 0, 0)
        event_layout.setSpacing(8)
        event_layout.addWidget(section("RECENT EVENTS  /  UTC"))
        self.recent = QPlainTextEdit()
        self.recent.setReadOnly(True)
        self.recent.setMaximumBlockCount(100)
        self.recent.setAccessibleName("실제 최근 이벤트")
        event_layout.addWidget(self.recent)
        workspace.addWidget(self.events_panel)
        workspace.setSizes([300, 150])
        workspace.setChildrenCollapsible(False)
        body.addWidget(workspace, 1)
        root.addLayout(body, 1)
        root.addWidget(rule())
        self.prompt_panel = QWidget()
        footer = QHBoxLayout(self.prompt_panel)
        footer.setContentsMargins(0, 0, 0, 0)
        prompt = QLabel("jack@guard >")
        prompt.setObjectName("prompt")
        footer.addWidget(prompt)
        self.command = CommandLine()
        self.command.submitted.connect(self.command_requested)
        footer.addWidget(self.command, 1)
        help_button = QPushButton("F1 HELP")
        help_button.clicked.connect(lambda: self.command_requested.emit("help"))
        footer.addWidget(help_button)
        self.quit_button = QPushButton("EXIT")
        self.quit_button.clicked.connect(lambda: self.command_requested.emit("exit"))
        footer.addWidget(self.quit_button)
        root.addWidget(self.prompt_panel)
        self.setTabOrder(self.command, self.lock_button)
        self.shortcuts = []
        for key, callback in [
            ("F1", lambda: self.command_requested.emit("help")),
            ("Ctrl+K", self.command.setFocus),
            ("Escape", self.back),
            ("Ctrl+Shift+L", lambda: self.command_requested.emit("lock")),
        ]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def back(self):
        if self.intro and self.intro.active:
            self.intro.finish("keyboard-skip")
        self.command.clear()
        self.command.setFocus()

    def write(self, text):
        self.console.appendPlainText(str(text))
        scroll = self.console.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def reveal_regions(self):
        return [
            self.header,
            self.state_panel,
            self.navigation,
            self.console_panel,
            self.events_panel,
            self.prompt_panel,
        ]

    def closeEvent(self, event):
        if self.intro:
            self.intro.finish("window-close")
        if (
            self.controller
            and self.controller.tray.isVisible()
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            self.hide()
            event.ignore()
        else:
            event.accept()
            if self.controller:
                self.controller.quit()
