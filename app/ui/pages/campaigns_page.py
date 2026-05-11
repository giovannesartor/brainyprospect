"""Página de Campanhas comerciais — agrupamento estratégico de leads."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import CampaignRepository, LeadRepository


class CampaignsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("Campanhas Comerciais")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch()
        self.refresh_btn = QPushButton("Atualizar"); self.refresh_btn.clicked.connect(self.reload)
        head.addWidget(self.refresh_btn)
        root.addLayout(head)

        # Form de criação
        form_card = QFrame(); form_card.setObjectName("card")
        fl = QFormLayout(form_card)
        fl.setContentsMargins(16, 14, 16, 14)
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Ex.: Contabilidades RS")
        self.desc_input = QTextEdit(); self.desc_input.setPlaceholderText("Descrição/objetivo")
        self.desc_input.setMaximumHeight(70)
        self.target_mode = QComboBox()
        self.target_mode.addItem("Venda Direta", "direct_sale")
        self.target_mode.addItem("Parceiros", "partners")
        fl.addRow("Nome", self.name_input)
        fl.addRow("Foco", self.target_mode)
        fl.addRow("Descrição", self.desc_input)
        actions = QHBoxLayout()
        self.create_btn = QPushButton("Criar campanha"); self.create_btn.setObjectName("primary")
        self.create_btn.clicked.connect(self._create)
        actions.addStretch(); actions.addWidget(self.create_btn)
        fl.addRow(actions)
        root.addWidget(form_card)

        # Tabela
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Nome", "Foco", "Leads", "Score médio", "Fechados", "Ações"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        self.reload()

    def _create(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Campanha", "Informe um nome.")
            return
        CampaignRepository.create(
            name=name,
            description=self.desc_input.toPlainText().strip(),
            target_mode=self.target_mode.currentData(),
        )
        self.name_input.clear()
        self.desc_input.clear()
        self.reload()

    def reload(self) -> None:
        rows = CampaignRepository.list_all()
        self.table.setRowCount(0)
        for c in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(c["id"])))
            self.table.setItem(r, 1, QTableWidgetItem(c["name"]))
            target = "Parceiros" if c["target_mode"] == "partners" else "Venda Direta"
            self.table.setItem(r, 2, QTableWidgetItem(target))
            self.table.setItem(r, 3, QTableWidgetItem(str(c["lead_count"])))
            self.table.setItem(r, 4, QTableWidgetItem(str(c["avg_score"])))
            self.table.setItem(r, 5, QTableWidgetItem(str(c["won"])))

            assign_btn = QPushButton("Adicionar leads")
            assign_btn.clicked.connect(lambda _=False, cid=c["id"]: self._assign_leads(cid))
            self.table.setCellWidget(r, 6, assign_btn)

    def _assign_leads(self, campaign_id: int) -> None:
        text, ok = QInputDialog.getText(
            self, "Adicionar leads",
            "IDs dos leads (separados por vírgula):"
        )
        if not ok:
            return
        try:
            ids = [int(x.strip()) for x in text.split(",") if x.strip().isdigit()]
        except Exception:
            ids = []
        if not ids:
            return
        n = CampaignRepository.assign_leads(campaign_id, ids)
        QMessageBox.information(self, "Campanha", f"{n} leads associados.")
        self.reload()
