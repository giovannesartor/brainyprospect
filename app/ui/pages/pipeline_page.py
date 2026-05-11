"""Pipeline CRM (Kanban) — leads por status com mover via combo."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadRepository
from app.services.intelligence import PRIORITY_LABEL

STAGES = [
    ("novo", "Novos", "#6366F1"),
    ("qualificado", "Qualificados", "#8B5CF6"),
    ("contatado", "Contatados", "#0EA5E9"),
    ("respondeu", "Responderam", "#22D3EE"),
    ("reuniao", "Reunião", "#F59E0B"),
    ("proposta", "Proposta", "#FB923C"),
    ("fechado", "Fechado", "#10B981"),
    ("perdido", "Perdido", "#6B7280"),
]


class StageColumn(QFrame):
    """Coluna do pipeline com leads de um status específico."""

    def __init__(self, status: str, title: str, color: str, on_change) -> None:
        super().__init__()
        self.status = status
        self.color = color
        self.on_change = on_change
        self.setObjectName("card")
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        header = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color};font-size:18px")
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("kanbanColTitle")
        self.count_lbl = QLabel("0")
        self.count_lbl.setObjectName("mutedSmall")
        header.addWidget(dot)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.count_lbl)
        lay.addLayout(header)

        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget{background:transparent;border:0}"
            "QListWidget::item{background:#0F1217;border:1px solid #1F2530;"
            "border-radius:8px;padding:8px;margin-bottom:6px;color:#E6E8EE}"
            "QListWidget::item:selected{border:1px solid #6366F1}"
        )
        self.list.itemDoubleClicked.connect(self._move_dialog)
        lay.addWidget(self.list, 1)

    def set_leads(self, leads: list[dict]) -> None:
        self.list.clear()
        self.count_lbl.setText(str(len(leads)))
        for L in leads:
            score = int(L.get("score") or 0)
            prio_label, prio_color = PRIORITY_LABEL.get(L.get("priority") or "media",
                                                       ("Média", "#FBBF24"))
            txt = (f"{L.get('name','—')}\n"
                   f"Score {score} · {prio_label}\n"
                   f"{L.get('city','')}/{L.get('state','')} · "
                   f"{L.get('ticket_estimate','') or '—'}")
            it = QListWidgetItem(txt)
            it.setData(Qt.UserRole, L["id"])
            it.setForeground(QColor("#E6E8EE"))
            self.list.addItem(it)

    def _move_dialog(self, item: QListWidgetItem) -> None:
        from PySide6.QtWidgets import QInputDialog
        choices = [f"{s[1]}" for s in STAGES]
        cur = next((i for i, s in enumerate(STAGES) if s[0] == self.status), 0)
        choice, ok = QInputDialog.getItem(
            self, "Mover lead", "Mover para:", choices, cur, False
        )
        if not ok:
            return
        new_status = STAGES[choices.index(choice)][0]
        lead_id = int(item.data(Qt.UserRole))
        LeadRepository.update(lead_id, status=new_status)
        self.on_change()


class PipelinePage(QWidget):
    """Visão Kanban do CRM."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("Pipeline Comercial")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch()
        self.mode_filter = QComboBox()
        self.mode_filter.addItem("Todos os tipos", "")
        self.mode_filter.addItem("Venda Direta", "direct_sale")
        self.mode_filter.addItem("Parceiros", "partners")
        self.mode_filter.currentIndexChanged.connect(self.reload)
        head.addWidget(self.mode_filter)
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.clicked.connect(self.reload)
        head.addWidget(self.refresh_btn)
        root.addLayout(head)

        self.summary_lbl = QLabel("")
        self.summary_lbl.setObjectName("mutedSmall")
        root.addWidget(self.summary_lbl)

        # área scrollável horizontal
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.cols_layout = QHBoxLayout(container)
        self.cols_layout.setSpacing(12)
        self.cols_layout.setContentsMargins(0, 0, 0, 0)

        self.columns: list[StageColumn] = []
        for status, title_, color in STAGES:
            col = StageColumn(status, title_, color, on_change=self.reload)
            self.cols_layout.addWidget(col)
            self.columns.append(col)
        self.cols_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.reload()

    def reload(self) -> None:
        mode = self.mode_filter.currentData() or None
        for col in self.columns:
            rows = LeadRepository.query(
                status=col.status,
                prospection_mode=mode,
                limit=200,
            )
            col.set_leads(rows)
        stats = LeadRepository.pipeline_stats()
        total = sum(stats.values()) or 1
        won = stats.get("fechado", 0)
        rate = round(100 * won / total, 1)
        self.summary_lbl.setText(
            f"Total: {sum(stats.values())} leads · Conversão: {rate}% "
            f"({won} fechados) · Em proposta: {stats.get('proposta', 0)}"
        )
