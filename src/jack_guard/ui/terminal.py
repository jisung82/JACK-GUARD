from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCompleter, QLineEdit

COMMANDS = (
    "help",
    "status",
    "lock",
    "privacy on",
    "privacy off",
    "monitor status",
    "monitor on",
    "monitor off",
    "process list",
    "logs",
    "logs clear",
    "settings",
    "version",
    "clear",
    "exit",
)

HELP = """JACK GUARD BUILT-IN COMMANDS
  status              실제 세션 / 프라이버시 / 감지 / 단축키 상태
  lock                Windows 잠금 요청 (해제: Windows 인증)
  privacy on | off    창 숨김 / 화면 가림 및 복원
  monitor status      감시 목록·예외·동작 확인
  monitor on | off    감지 활성화 / 중지 (설정 보호 적용)
  process list        현재 사용자 프로세스 조회 (비동기)
  logs                로컬 이벤트 조회
  logs clear          로그 삭제 (설정 보호 및 확인 적용)
  settings            설정 열기
  version             버전 확인
  clear               콘솔 출력 지우기
  exit                정상 종료
  help                이 도움말

Tab 자동완성 · ↑/↓ 명령 기록 · F1 도움말 · Esc 입력 취소
앱 내부 명령만 지원합니다. 셸·PowerShell은 실행하지 않습니다."""


class CommandLine(QLineEdit):
    submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("command")
        self.setAccessibleName("JACK GUARD 명령어 입력")
        self.setPlaceholderText("help  /  Tab to complete")
        self.setMaxLength(256)
        self.history = []
        self.position = 0
        self.draft = ""
        self.matches = []
        self.cycle = -1
        completer = QCompleter(list(COMMANDS), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
        self.returnPressed.connect(self.submit)
        self.textEdited.connect(self.reset_completion)

    def reset_completion(self, text=""):
        self.matches = []
        self.cycle = -1

    def submit(self):
        text = self.text().strip()
        if not text:
            return
        if not self.history or self.history[-1] != text:
            self.history.append(text)
            self.history = self.history[-100:]
        self.position = len(self.history)
        self.draft = ""
        self.clear()
        self.completer().popup().hide()
        self.reset_completion()
        self.submitted.emit(text)

    def event(self, event):
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key.Key_Tab and self.text():
            self.complete()
            return True
        return super().event(event)

    def complete(self):
        if not self.matches:
            self.matches = [c for c in COMMANDS if c.startswith(self.text().lower())]
        if self.matches:
            self.cycle = (self.cycle + 1) % len(self.matches)
            self.setText(self.matches[self.cycle])
            self.completer().popup().hide()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            if self.position == len(self.history):
                self.draft = self.text()
            change = -1 if key == Qt.Key.Key_Up else 1
            self.position = max(0, min(len(self.history), self.position + change))
            self.setText(
                self.history[self.position] if self.position < len(self.history) else self.draft
            )
            self.completer().popup().hide()
            self.reset_completion()
            return
        if key == Qt.Key.Key_Escape:
            self.clear()
            self.completer().popup().hide()
            self.reset_completion()
            return
        super().keyPressEvent(event)
