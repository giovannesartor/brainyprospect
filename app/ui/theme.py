"""Sistema de temas: dark + light, totalmente funcional, persistido via QSettings."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


# ---------------------------------------------------------------- paletas
DARK = {
    "bg": "#0F1115",
    "bg_alt": "#0B0D11",
    "panel": "#14181F",
    "panel_alt": "#161B24",
    "border": "#1F242E",
    "border_strong": "#232936",
    "input_bg": "#0F141B",
    "text": "#E6E8EE",
    "text_dim": "#8A93A6",
    "text_mute": "#6B7280",
    "text_faint": "#4B5563",
    "white": "#FFFFFF",
    "accent": "#6366F1",
    "accent_hi": "#818CF8",
    "accent_lo": "#4F46E5",
    "accent_grad2": "#22D3EE",
    "danger": "#EF4444",
    "warn": "#F59E0B",
    "ok": "#10B981",
    "hover": "#161A22",
    "selected": "#1B2230",
    "tooltip_bg": "#1B2230",
    "header_title": "#FFFFFF",
    "scrollbar": "#2A2F40",
    "scrollbar_hover": "#3A4258",
    "kanban_col": "#0E1218",
}

LIGHT = {
    "bg": "#F6F7F9",
    "bg_alt": "#FFFFFF",
    "panel": "#FFFFFF",
    "panel_alt": "#FAFBFC",
    "border": "#E4E7EC",
    "border_strong": "#D0D5DD",
    "input_bg": "#FFFFFF",
    "text": "#1F2937",
    "text_dim": "#475467",
    "text_mute": "#667085",
    "text_faint": "#98A2B3",
    "white": "#FFFFFF",
    "accent": "#4F46E5",
    "accent_hi": "#6366F1",
    "accent_lo": "#4338CA",
    "accent_grad2": "#0EA5E9",
    "danger": "#DC2626",
    "warn": "#D97706",
    "ok": "#059669",
    "hover": "#F1F3F8",
    "selected": "#EEF0FF",
    "tooltip_bg": "#1F2937",
    "header_title": "#101828",
    "scrollbar": "#D0D5DD",
    "scrollbar_hover": "#98A2B3",
    "kanban_col": "#F2F4F7",
}


def _qss(c: dict[str, str]) -> str:
    return f"""
* {{ font-family: "Helvetica Neue", Inter, Arial, sans-serif; }}

QMainWindow, QWidget {{ background-color: {c['bg']}; color: {c['text']}; }}

#sidebar {{
    background-color: {c['bg_alt']};
    border-right: 1px solid {c['border']};
}}
#sidebar QLabel#brand {{
    color: {c['header_title']};
    font-size: 16px; font-weight: 700;
    padding: 18px 18px 8px 18px; letter-spacing: 0.3px;
}}
#sidebar QLabel#brand_sub {{
    color: {c['text_mute']};
    font-size: 11px; padding: 0 18px 18px 18px;
    text-transform: uppercase; letter-spacing: 1.4px;
}}
QPushButton#nav {{
    text-align: left; padding: 10px 16px; margin: 2px 10px;
    border-radius: 8px; color: {c['text_dim']};
    font-size: 13px; background: transparent; border: none;
}}
QPushButton#nav:hover {{ background: {c['hover']}; color: {c['header_title']}; }}
QPushButton#nav:checked {{
    background: {c['selected']}; color: {c['header_title']};
    border-left: 3px solid {c['accent']}; padding-left: 13px;
}}

QPushButton#navParent {{
    text-align: left; padding: 9px 16px; margin: 6px 10px 2px 10px;
    border-radius: 8px; color: {c['text']};
    font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
    background: transparent; border: none;
}}
QPushButton#navParent:hover {{ background: {c['hover']}; }}

QPushButton#navChild {{
    text-align: left; padding: 7px 16px 7px 38px; margin: 1px 10px;
    border-radius: 6px; color: {c['text_dim']};
    font-size: 12px; background: transparent; border: none;
}}
QPushButton#navChild:hover {{ background: {c['hover']}; color: {c['text']}; }}
QPushButton#navChild:checked {{
    background: {c['selected']}; color: {c['header_title']};
    border-left: 2px solid {c['accent']}; padding-left: 36px;
}}

QLabel#sidebarSection {{
    color: {c['text_faint']}; font-size: 10px;
    font-weight: 700; letter-spacing: 1.6px;
    padding: 14px 18px 4px 18px;
}}

#header {{ background: {c['bg']}; border-bottom: 1px solid {c['border']}; }}
#header QLabel#title {{ font-size: 20px; font-weight: 600; color: {c['header_title']}; }}
#header QLabel#subtitle {{ color: {c['text_dim']}; font-size: 12px; }}

QFrame#card {{
    background-color: {c['panel']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}
QLabel#cardTitle {{ color: {c['text_dim']}; font-size: 11px;
    text-transform: uppercase; letter-spacing: 1.2px; }}
QLabel#cardValue {{ color: {c['header_title']}; font-size: 26px; font-weight: 700; }}
QLabel#cardHint {{ color: {c['text_mute']}; font-size: 11px; }}

QFrame#sectionCard {{
    background-color: {c['panel']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QLabel#sectionHead {{
    color: {c['header_title']}; font-size: 14px;
    font-weight: 700; padding: 0;
}}
QLabel#sectionSub {{ color: {c['text_dim']}; font-size: 11px; }}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px; padding: 8px 10px;
    color: {c['text']}; selection-background-color: {c['accent']};
    min-height: 18px;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {c['accent']};
}}
QPlainTextEdit, QTextEdit {{ font-family: "SF Mono", Menlo, Consolas, monospace; }}

QPushButton {{
    background-color: {c['selected']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px; color: {c['text']};
    padding: 8px 16px; font-weight: 500;
}}
QPushButton:hover {{ background-color: {c['hover']}; }}
QPushButton:disabled {{ color: {c['text_faint']}; background-color: {c['panel_alt']}; }}

QPushButton#primary {{
    background-color: {c['accent']};
    border: 1px solid {c['accent']};
    color: #FFFFFF; font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {c['accent_lo']}; }}
QPushButton#primary:disabled {{ background-color: {c['border_strong']};
    border-color: {c['border_strong']}; color: {c['text_mute']}; }}

QPushButton#ghost {{ background: transparent; border: 1px solid {c['border_strong']}; }}
QPushButton#ghost:hover {{ background-color: {c['hover']}; }}

QPushButton#danger {{
    background: {c['danger']}; color: #FFFFFF; border: 1px solid {c['danger']};
}}

QPushButton#chip {{
    background: transparent;
    border: 1px solid {c['border_strong']};
    border-radius: 16px; padding: 6px 14px;
    color: {c['text_dim']}; font-size: 11px; font-weight: 600;
}}
QPushButton#chip:checked {{
    background: {c['accent']}; color: #FFFFFF; border: 1px solid {c['accent']};
}}
QPushButton#chip:hover:!checked {{ background: {c['hover']}; color: {c['text']}; }}

QPushButton#seg {{
    background: {c['panel']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px; padding: 10px 14px;
    color: {c['text_dim']}; font-weight: 600; font-size: 13px;
}}
QPushButton#seg:hover:!checked {{ background: {c['hover']}; color: {c['text']}; }}
QPushButton#seg:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent']}, stop:1 {c['accent_lo']});
    color: #FFFFFF; border: 1px solid {c['accent']};
}}

QTableView, QTreeView, QListView {{
    background-color: {c['panel']};
    alternate-background-color: {c['panel_alt']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 10px; color: {c['text']};
    selection-background-color: {c['selected']};
    selection-color: {c['header_title']};
}}
QHeaderView::section {{
    background-color: {c['panel_alt']}; color: {c['text_dim']};
    padding: 8px; border: none;
    border-bottom: 1px solid {c['border']}; font-weight: 600;
}}

QProgressBar {{
    background-color: {c['panel_alt']};
    border: 1px solid {c['border']};
    border-radius: 6px; text-align: center;
    color: {c['text']}; height: 14px;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent']}, stop:1 {c['accent_grad2']});
    border-radius: 6px;
}}

QStatusBar {{ background: {c['bg_alt']}; border-top: 1px solid {c['border']};
    color: {c['text_mute']}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {c['scrollbar']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c['scrollbar_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {c['scrollbar']}; border-radius: 4px; min-width: 30px; }}

QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 10px; top: -1px;
    background: {c['panel']}; }}
QTabBar::tab {{
    background: transparent; color: {c['text_dim']};
    padding: 8px 16px; margin-right: 4px;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{ background: {c['panel']}; color: {c['header_title']}; }}

QCheckBox {{ color: {c['text']}; spacing: 8px; padding: 2px 0; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {c['border_strong']}; background: {c['input_bg']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}

QToolTip {{ color: #FFFFFF; background-color: {c['tooltip_bg']};
    border: 1px solid {c['border_strong']}; padding: 4px; }}

QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; color: {c['text']}; }}
QMenu::item:selected {{ background: {c['selected']}; color: {c['header_title']}; }}

/* Títulos reutilizáveis (auto-adaptam ao tema) */
QLabel#pageTitle {{ color: {c['header_title']}; font-size: 20px; font-weight: 700; }}
QLabel#pageTitleBig {{ color: {c['header_title']}; font-size: 24px; font-weight: 700; }}
QLabel#cardName {{ color: {c['header_title']}; font-size: 15px; font-weight: 700; padding: 4px 0; }}
QLabel#kanbanColTitle {{ color: {c['header_title']}; font-size: 13px; font-weight: 700; }}
QLabel#sidebarBrandName {{ color: {c['header_title']}; font-size: 15px; font-weight: 700; padding: 0; }}
QLabel#mutedHint {{ color: {c['text_dim']}; font-size: 12px; font-weight: 600; }}

/* Labels reutilizáveis adaptáveis ao tema */
QLabel#intro {{ color: {c['text_dim']}; font-size: 13px; }}
QLabel#muted {{ color: {c['text_dim']}; font-size: 12px; }}
QLabel#mutedSmall {{ color: {c['text_mute']}; font-size: 11px; }}
QLabel#fieldLabel {{ color: {c['text_dim']}; font-size: 11px; font-weight: 600; }}
QLabel#sectionHeader {{ color: {c['header_title']}; font-size: 13px; font-weight: 700; }}
QLabel#warnHeader {{ color: {c['warn']}; font-weight: 700; font-size: 14px; margin-top: 8px; }}
QLabel#dangerHeader {{ color: {c['danger']}; font-weight: 700; font-size: 14px; margin-top: 8px; }}
QLabel#footerText {{ color: {c['text_faint']}; font-size: 10px; padding: 10px 18px; }}
"""


# ---------------------------------------------------------------- gestor
_THEME_KEY = "ui/theme"
_current_theme: str = "dark"
_listeners: list = []


def current_theme() -> str:
    return _current_theme


def colors() -> dict[str, str]:
    return DARK if _current_theme == "dark" else LIGHT


def on_theme_changed(callback) -> None:
    """Registra um callback chamado sempre que o tema mudar."""
    if callback not in _listeners:
        _listeners.append(callback)


def _emit() -> None:
    for cb in list(_listeners):
        try:
            cb(_current_theme)
        except Exception:  # noqa: BLE001
            pass


def _apply_palette(app: QApplication, c: dict[str, str]) -> None:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(c["bg"]))
    pal.setColor(QPalette.WindowText, QColor(c["text"]))
    pal.setColor(QPalette.Base, QColor(c["panel"]))
    pal.setColor(QPalette.AlternateBase, QColor(c["panel_alt"]))
    pal.setColor(QPalette.Text, QColor(c["text"]))
    pal.setColor(QPalette.Button, QColor(c["selected"]))
    pal.setColor(QPalette.ButtonText, QColor(c["text"]))
    pal.setColor(QPalette.Highlight, QColor(c["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.ToolTipBase, QColor(c["tooltip_bg"]))
    pal.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    app.setPalette(pal)


def apply_theme(theme: str = "") -> None:
    global _current_theme
    app = QApplication.instance()
    if app is None:
        return
    if theme not in ("dark", "light"):
        # restore from settings
        s = QSettings("BrainyProspect", "BrainyProspect")
        theme = str(s.value(_THEME_KEY, "dark"))
        if theme not in ("dark", "light"):
            theme = "dark"
    _current_theme = theme
    c = colors()
    app.setStyle("Fusion")
    _apply_palette(app, c)
    app.setStyleSheet(_qss(c))
    s = QSettings("BrainyProspect", "BrainyProspect")
    s.setValue(_THEME_KEY, theme)
    _emit()


def toggle_theme() -> str:
    apply_theme("light" if _current_theme == "dark" else "dark")
    return _current_theme


# ---------------------------------------------------------------- compat
def apply_dark_theme(app: QApplication) -> None:
    """Mantido por compat: agora aplica o tema persistido (default dark)."""
    apply_theme("")
