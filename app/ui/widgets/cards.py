"""Widgets reutilizáveis: cards de estatística, badges, etc."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0", hint: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(110)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(6)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("cardTitle")

        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("cardValue")

        self.hint_lbl = QLabel(hint)
        self.hint_lbl.setObjectName("cardHint")
        self.hint_lbl.setWordWrap(True)

        lay.addWidget(self.title_lbl)
        lay.addWidget(self.value_lbl)
        lay.addWidget(self.hint_lbl)
        lay.addStretch()

    def set_value(self, value: str, hint: str = "") -> None:
        self.value_lbl.setText(str(value))
        if hint:
            self.hint_lbl.setText(hint)


class SectionTitle(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("cardName")
