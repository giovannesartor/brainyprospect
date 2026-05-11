"""Tela de Logs/Exportações: visualiza arquivos exportados e log do dia."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from datetime import datetime

from app.database import ExportRepository
from app.paths import LOGS_DIR
from app.ui.widgets.cards import SectionTitle


class LogsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(SectionTitle("Logs e exportações"))

        splitter = QSplitter(Qt.Vertical)

        # Exportações
        self.exports_table = QTableWidget(0, 4)
        self.exports_table.setHorizontalHeaderLabels(["Data", "Formato", "Linhas", "Arquivo"])
        self.exports_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.exports_table.verticalHeader().setVisible(False)
        splitter.addWidget(self.exports_table)

        # Log do dia
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        splitter.addWidget(self.log_view)
        splitter.setSizes([220, 420])
        root.addWidget(splitter, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.setObjectName("ghost")
        self.refresh_btn.clicked.connect(self.reload)
        actions.addWidget(self.refresh_btn)
        root.addLayout(actions)

        self.reload()

    def reload(self) -> None:
        rows = ExportRepository.list_recent(50)
        self.exports_table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            self.exports_table.setItem(r, 0, QTableWidgetItem(e["created_at"].strftime("%d/%m/%Y %H:%M")))
            self.exports_table.setItem(r, 1, QTableWidgetItem(e["format"].upper()))
            self.exports_table.setItem(r, 2, QTableWidgetItem(str(e["rows"])))
            self.exports_table.setItem(r, 3, QTableWidgetItem(e["file"]))

        # carrega log do dia
        log_file = LOGS_DIR / f"brainyprospect_{datetime.now().strftime('%Y-%m-%d')}.log"
        if log_file.exists():
            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
                # mantém últimas ~600 linhas
                lines = content.splitlines()[-600:]
                self.log_view.setPlainText("\n".join(lines))
                self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
            except Exception as e:  # noqa: BLE001
                self.log_view.setPlainText(f"Falha ao ler log: {e}")
        else:
            self.log_view.setPlainText("Sem log do dia ainda.")
