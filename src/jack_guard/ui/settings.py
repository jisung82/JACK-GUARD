from copy import deepcopy

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jack_guard import __version__
from jack_guard.config.store import validate
from jack_guard.core import startup
from jack_guard.security.passwords import hash_password


class SettingsDialog(QDialog):
    def __init__(self, controller):
        super().__init__(controller.window)
        self.c = controller
        self.value = deepcopy(controller.settings)
        self.setWindowTitle("JACK GUARD · 설정")
        self.resize(700, 650)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        general = QWidget()
        form = QFormLayout(general)
        self.lock = QLineEdit(self.value.lock_hotkey)
        self.privacy = QLineEdit(self.value.privacy_hotkey)
        form.addRow("Windows 잠금 단축키", self.lock)
        form.addRow("프라이버시 단축키", self.privacy)
        form.addRow(QLabel("예: Ctrl+Alt+L · 충돌 시 저장하지 않습니다."))
        self.checks = {}
        for key, label in [
            ("monitor", "게임 실행 감지 활성화"),
            ("notifications", "트레이 알림"),
            ("overlay", "프라이버시 모드에서 모든 화면 가림"),
            ("terminate", "지정 프로세스 자동 종료 (명시적 동의 필요)"),
        ]:
            check = QCheckBox(label)
            check.setChecked(getattr(self.value, key))
            self.checks[key] = check
            form.addRow(check)
        self.checks["terminate"].clicked.connect(self.confirm_termination)
        self.startup = QCheckBox("Windows 로그인 시 자동 실행")
        self.startup.setChecked(startup.is_enabled())
        form.addRow(self.startup)
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(self.value.retention_days)
        form.addRow("로그 보존 일수", self.days)
        form.addRow(QLabel("화면 가림·창 숨김은 Windows 잠금이 아닙니다."))
        self.tabs.addTab(general, "일반")
        self.lists = {}
        for key, title in [("games", "감시 실행파일"), ("exceptions", "예외 실행파일")]:
            page = QWidget()
            box = QVBoxLayout(page)
            box.addWidget(QLabel("전체 경로로 비교합니다. 예외 목록이 우선합니다."))
            listing = QListWidget()
            listing.addItems(getattr(self.value, key))
            self.lists[key] = listing
            box.addWidget(listing)
            buttons = QHBoxLayout()
            add = QPushButton(".exe 추가")
            add.clicked.connect(lambda checked=False, k=key: self.add_path(k))
            remove = QPushButton("선택 제거")
            remove.clicked.connect(lambda checked=False, k=key: self.remove_path(k))
            buttons.addWidget(add)
            buttons.addWidget(remove)
            box.addLayout(buttons)
            self.tabs.addTab(page, title)
        security = QWidget()
        sec = QVBoxLayout(security)
        sec.addWidget(
            QLabel(
                "설정 비밀번호는 이 앱의 설정 화면만 보호합니다.\n"
                "Windows 인증이나 관리자 권한을 제공하지 않습니다."
            )
        )
        for text, action in [
            ("비밀번호 설정 / 변경", self.set_password),
            ("비밀번호 제거", self.remove_password),
            ("설정 내보내기 (비밀번호 제외)", self.export_settings),
            ("설정 가져오기 (감지·종료 비활성화)", self.import_settings),
        ]:
            button = QPushButton(text)
            button.clicked.connect(action)
            sec.addWidget(button)
        sec.addWidget(
            QLabel(
                "분실 시 앱을 종료하고:\nJACK-GUARD.exe --reset-settings\n"
                "설정·비밀번호·자동 시작을 초기화합니다. 로그는 보존됩니다."
            )
        )
        sec.addStretch()
        self.tabs.addTab(security, "설정 보호")
        logs = QWidget()
        logbox = QVBoxLayout(logs)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlainText(controller.events.read())
        logbox.addWidget(self.log_view)
        clear = QPushButton("로컬 로그 모두 삭제")
        clear.clicked.connect(self.clear_logs)
        logbox.addWidget(clear)
        self.tabs.addTab(logs, "로그")
        about = QLabel(
            f"JACK GUARD {__version__}\nWindows 10/11 x64 · 개인용 프라이버시 보조 도구\n\n"
            "네트워크 전송 없음 · 관리자 권한 불필요\n"
            "코드 서명 없음: SmartScreen 경고가 표시될 수 있습니다.\n\n"
            "업데이트 확인: 공개 저장소 승인 후 README의 Releases에서 수동 확인\n"
            "영어 번역 확장 구조 포함 · 현재 UI: 한국어"
        )
        about.setWordWrap(True)
        self.tabs.addTab(about, "정보")
        footer = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        footer.accepted.connect(self.save)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def confirm_termination(self, checked):
        if (
            checked
            and QMessageBox.warning(
                self,
                "프로세스 종료 동의",
                "감시 목록의 본인 프로세스를 자동 종료합니다.\n"
                "저장하지 않은 게임 진행이 손실될 수 있습니다. 활성화하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            self.checks["terminate"].setChecked(False)

    def add_path(self, key):
        path, _ = QFileDialog.getOpenFileName(self, "게임 실행파일 선택", "", "실행파일 (*.exe)")
        listing = self.lists[key]
        if path and path not in [listing.item(i).text() for i in range(listing.count())]:
            listing.addItem(path)

    def remove_path(self, key):
        listing = self.lists[key]
        for item in listing.selectedItems():
            listing.takeItem(listing.row(item))

    def collect(self):
        from dataclasses import asdict

        result = deepcopy(self.value)
        result.lock_hotkey, result.privacy_hotkey = self.lock.text(), self.privacy.text()
        for key, check in self.checks.items():
            setattr(result, key, check.isChecked())
        for key, listing in self.lists.items():
            setattr(result, key, [listing.item(i).text() for i in range(listing.count())])
        result.retention_days = self.days.value()
        return validate(asdict(result))

    def set_password(self):
        first, ok = QInputDialog.getText(
            self, "설정 비밀번호", "새 비밀번호 (8~256자)", QLineEdit.EchoMode.Password
        )
        if not ok:
            return
        second, ok = QInputDialog.getText(self, "확인", "다시 입력", QLineEdit.EchoMode.Password)
        if ok:
            try:
                if first != second:
                    raise ValueError("비밀번호가 일치하지 않습니다.")
                self.value.password = hash_password(first)
                QMessageBox.information(self, "설정", "저장 버튼을 누르면 적용됩니다.")
            except ValueError as error:
                QMessageBox.warning(self, "설정", str(error))

    def remove_password(self):
        self.value.password = {}
        QMessageBox.information(self, "설정", "저장 버튼을 누르면 비밀번호가 제거됩니다.")

    def export_settings(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "설정 내보내기", "jack-guard.json", "JSON (*.json)"
        )
        if path:
            try:
                self.c.store.export(self.collect(), path)
            except (ValueError, OSError) as error:
                QMessageBox.warning(self, "내보내기 실패", str(error))

    def import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, "설정 가져오기", "", "JSON (*.json)")
        if path:
            try:
                value = self.c.store.import_file(path, self.c.settings.password)
                self.c.apply_settings(value, self.startup.isChecked())
                self.accept()
            except (ValueError, TypeError, OSError) as error:
                QMessageBox.warning(self, "가져오기 실패", str(error))

    def clear_logs(self):
        if QMessageBox.question(self, "로그 삭제", "모든 로컬 로그를 삭제하시겠습니까?") == (
            QMessageBox.StandardButton.Yes
        ):
            try:
                self.c.events.clear()
                self.log_view.clear()
                self.c.refresh()
            except OSError:
                QMessageBox.warning(self, "삭제 실패", "로그 파일에 접근할 수 없습니다.")

    def save(self):
        try:
            self.c.apply_settings(self.collect(), self.startup.isChecked())
            self.accept()
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "저장 실패", str(error))
