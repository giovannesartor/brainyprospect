"""Componente: seletor de Estratégia Comercial (Venda Direta / Parceiros / Ambos)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import colors as theme_colors


SEGMENT_QSS = """
QPushButton#segment {
    background: transparent;
    border: 1px solid #232936;
    color: #C4C9D4;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton#segment:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366F1, stop:1 #4F46E5);
    color: #FFFFFF;
    border: 1px solid #6366F1;
}
QPushButton#segment:hover:!checked { background: #161A22; color: #FFFFFF; }
QPushButton#segLeft   { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#segMid    { border-radius: 0; }
QPushButton#segRight  { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
"""


class ModeSwitch(QWidget):
    """Segmented control: direct_sale | both | partners."""
    mode_changed = Signal(str)

    def __init__(self, initial: str = "direct_sale") -> None:
        super().__init__()
        self.setStyleSheet(SEGMENT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        title = QLabel("Estratégia Comercial")
        title.setStyleSheet(
            f"color:{theme_colors()['text_dim']};font-size:11px;text-transform:uppercase;"
            "letter-spacing:1.2px;font-weight:600;"
        )
        outer.addWidget(title)

        row = QHBoxLayout(); row.setSpacing(0); row.setContentsMargins(0, 0, 0, 0)

        self.btn_direct = self._make_btn("🎯  Venda Direta", "segLeft")
        self.btn_both = self._make_btn("⇄  Ambos", "segMid")
        self.btn_partners = self._make_btn("🤝  Parceiros", "segRight")

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for b in (self.btn_direct, self.btn_both, self.btn_partners):
            row.addWidget(b)
            self._group.addButton(b)

        # mapping
        self._mode_by_btn = {
            self.btn_direct: "direct_sale",
            self.btn_both: "both",
            self.btn_partners: "partners",
        }
        for b in self._mode_by_btn:
            b.clicked.connect(lambda _=False, btn=b: self._emit(btn))

        outer.addLayout(row)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            f"color:{theme_colors()['text_mute']};font-size:11px;padding-top:4px;"
        )
        outer.addWidget(self.hint)

        self.set_mode(initial)

    def _make_btn(self, text: str, name: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("segment")
        b.setProperty("class", name)
        # combine ids: object name + class for QSS specificity
        b.setObjectName(name)  # use specific name
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        # também marca como segment
        b.setProperty("segment", True)
        # aplicar estilo via setObjectName combinado
        c = theme_colors()
        b.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid """ + c['border_strong'] + """;
                color: """ + c['text'] + """;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 """ + c['accent'] + ", stop:1 " + c['accent_lo'] + """);
                color: #FFFFFF;
                border: 1px solid """ + c['accent'] + """;
            }
            QPushButton:hover:!checked { background: """ + c['hover'] + "; color: " + c['header_title'] + """; }
        """ + (
            "QPushButton { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }"
            if name == "segLeft" else
            "QPushButton { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }"
            if name == "segRight" else
            "QPushButton { border-radius: 0; border-left: 0; border-right: 0; }"
        ))
        return b

    def _emit(self, btn: QPushButton) -> None:
        mode = self._mode_by_btn.get(btn, "direct_sale")
        self._update_hint(mode)
        self.mode_changed.emit(mode)

    def _update_hint(self, mode: str) -> None:
        if mode == "partners":
            self.hint.setText("A IA buscará canais de indicação (contabilidades, advogados, "
                              "consultorias) que possam indicar clientes recorrentes.")
        elif mode == "both":
            self.hint.setText("Roda ambas as estratégias e separa os leads por categoria.")
        else:
            self.hint.setText("A IA buscará clientes finais com sinais reais de demanda "
                              "(crescimento, captação, M&A, holdings, expansão).")

    def set_mode(self, mode: str) -> None:
        if mode == "partners":
            self.btn_partners.setChecked(True)
        elif mode == "both":
            self.btn_both.setChecked(True)
        else:
            self.btn_direct.setChecked(True)
        self._update_hint(mode)

    def mode(self) -> str:
        for b, m in self._mode_by_btn.items():
            if b.isChecked():
                return m
        return "direct_sale"

    def highlight_recommendation(self, recommended: str) -> None:
        """Mostra um aviso sobre o modo recomendado pela IA."""
        if recommended not in ("direct_sale", "partners"):
            return
        label = "Parceiros" if recommended == "partners" else "Venda Direta"
        self.hint.setText(f"💡 IA sugere começar por: {label}.  " + self.hint.text())
