from PySide6.QtGui import QFont

BG = "#090B0D"
SURFACE = "#101316"
BORDER = "#2A3035"
TEXT = "#E6E8EA"
MUTED = "#89939B"
ACCENT = "#B8F36B"


def terminal_font(size=10):
    font = QFont()
    font.setFamilies(["Cascadia Mono", "JetBrains Mono", "Consolas", "Malgun Gothic"])
    font.setPointSizeF(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


STYLE = """
QWidget { background:#090B0D; color:#E6E8EA; font-size:13px; }
QLabel#brand { font-size:23px; font-weight:600; letter-spacing:2px; }
QLabel#muted, QLabel#section { color:#89939B; }
QLabel#section { font-size:11px; letter-spacing:1px; }
QLabel#value { font-size:14px; }
QLabel#prompt { color:#B8F36B; font-size:14px; }
QFrame#rule { background:#2A3035; max-height:1px; min-height:1px; border:0; }
QPushButton { background:transparent; border:1px solid #2A3035; border-radius:0;
              padding:9px 12px; text-align:left; }
QPushButton:hover { background:#171B1F; border-color:#89939B; }
QPushButton:focus { border:1px solid #B8F36B; }
QPushButton:pressed { background:#2A3035; }
QPushButton#nav { border:0; border-left:2px solid transparent; padding:11px 8px; }
QPushButton#nav:hover, QPushButton#nav:focus { border-left:2px solid #B8F36B; }
QPushButton#primary { color:#E6E8EA; border-color:#58626B; }
QPlainTextEdit, QTextEdit { background:#101316; border:1px solid #2A3035;
                          selection-background-color:#36492A; padding:10px; }
QLineEdit, QListWidget, QSpinBox, QComboBox { background:#101316; border:1px solid #2A3035;
                         padding:7px; selection-background-color:#36492A; }
QLineEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus { border-color:#B8F36B; }
QLineEdit#command { background:#090B0D; border:0; font-size:14px; padding:10px 4px; }
QLineEdit#command:focus { border-bottom:1px solid #58626B; }
QTabWidget::pane { border:1px solid #2A3035; }
QTabBar::tab { background:#101316; color:#89939B; padding:10px 12px; border:0; }
QTabBar::tab:selected { color:#B8F36B; border-bottom:1px solid #B8F36B; }
QCheckBox { spacing:9px; padding:6px 0; }
QCheckBox::indicator { width:13px; height:13px; border:1px solid #58626B; background:#101316; }
QCheckBox::indicator:checked { background:#B8F36B; border-color:#B8F36B; }
QCheckBox:focus { color:#B8F36B; }
QMenu { background:#101316; border:1px solid #2A3035; }
QMenu::item { padding:8px 24px; }
QMenu::item:selected { background:#171B1F; color:#B8F36B; }
QSplitter::handle { background:#090B0D; height:10px; }
QScrollBar:vertical { width:8px; background:#101316; }
QScrollBar::handle:vertical { background:#2A3035; min-height:24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QToolTip { background:#171B1F; color:#E6E8EA; border:1px solid #58626B; padding:5px; }
"""
