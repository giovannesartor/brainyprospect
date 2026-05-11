"""Tela de Histórico de pesquisas."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import SearchRepository
from app.ui.widgets.cards import SectionTitle


class HistoryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(SectionTitle("Histórico de pesquisas"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Data", "Entrada", "Nicho(s)", "Cidade", "Total"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.setObjectName("ghost")
        self.refresh_btn.clicked.connect(self.reload)
        actions.addWidget(self.refresh_btn)
        root.addLayout(actions)

        self.reload()

    def reload(self) -> None:
        rows = SearchRepository.list_recent(200)
        self.table.setRowCount(len(rows))
        for r, s in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(s["created_at"].strftime("%d/%m/%Y %H:%M")))
            self.table.setItem(r, 1, QTableWidgetItem(s["input"]))
            self.table.setItem(r, 2, QTableWidgetItem(s["niche"]))
            self.table.setItem(r, 3, QTableWidgetItem(s["city"]))
            self.table.setItem(r, 4, QTableWidgetItem(str(s["total"])))
