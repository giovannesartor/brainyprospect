"""Páginas reutilizáveis baseadas em filtros pré-aplicados sobre LeadsPage,
e uma 'placeholder page' visualmente premium para módulos em construção."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.leads_page import LeadsPage


class FilteredLeadsPage(LeadsPage):
    """Variação de LeadsPage com filtros pré-aplicados via dict."""

    def __init__(self, **preset) -> None:
        super().__init__()
        # Aplica preset: {"priority": "maxima", "mode": "partners", ...}
        if "priority" in preset:
            for i in range(self.priority_filter.count()):
                if self.priority_filter.itemData(i) == preset["priority"]:
                    self.priority_filter.setCurrentIndex(i)
                    break
        if "mode" in preset:
            for i in range(self.mode_filter.count()):
                if self.mode_filter.itemData(i) == preset["mode"]:
                    self.mode_filter.setCurrentIndex(i)
                    break
        if "min_score" in preset:
            self.min_score.setValue(preset["min_score"])
        if "tag" in preset:
            self.search_input.setText(preset["tag"])
        self.reload()


class DecisoresPage(QWidget):
    """Tabela apenas com leads que possuem decisores identificados."""

    def __init__(self) -> None:
        super().__init__()
        from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

        from app.database import LeadRepository

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        title = QLabel("Decisores Identificados")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        root.addWidget(QLabel(
            "CEOs, fundadores, sócios e diretores extraídos automaticamente dos sites."
        ))

        self._LeadRepository = LeadRepository
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Decisor", "Cargo", "Empresa", "Cidade", "Site", "Score"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        self._TableWidgetItem = QTableWidgetItem
        self.reload()

    def reload(self) -> None:
        rows = self._LeadRepository.query(limit=2000)
        self.table.setRowCount(0)
        for L in rows:
            dms = L.get("decision_makers") or []
            if not isinstance(dms, list):
                continue
            for d in dms:
                if not isinstance(d, dict):
                    continue
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, self._TableWidgetItem(d.get("name", "")))
                self.table.setItem(r, 1, self._TableWidgetItem(d.get("role", "")))
                self.table.setItem(r, 2, self._TableWidgetItem(L.get("name", "")))
                self.table.setItem(
                    r, 3, self._TableWidgetItem(f"{L.get('city','')}/{L.get('state','')}")
                )
                self.table.setItem(r, 4, self._TableWidgetItem(L.get("website", "")))
                self.table.setItem(r, 5, self._TableWidgetItem(str(L.get("score", 0))))


class PlaceholderPage(QWidget):
    """Página estilizada para módulos em construção."""

    def __init__(self, title: str, description: str,
                 features: list[str] | None = None,
                 emoji: str = "✨") -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 48, 48, 48)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(720)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 40, 40, 40)
        cl.setSpacing(16)
        cl.setAlignment(Qt.AlignCenter)

        big = QLabel(emoji)
        big.setAlignment(Qt.AlignCenter)
        big.setStyleSheet("font-size:54px")
        cl.addWidget(big)

        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setObjectName("pageTitleBig")
        cl.addWidget(t)

        d = QLabel(description)
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        d.setStyleSheet("color:#8A93A6;font-size:13px;line-height:18px")
        cl.addWidget(d)

        badge = QLabel("EM BREVE")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366F1,stop:1 #22D3EE);"
            "color:#0F1115;padding:6px 18px;border-radius:14px;"
            "font-weight:700;font-size:11px;letter-spacing:1.6px;max-width:120px"
        )
        cl.addWidget(badge, alignment=Qt.AlignCenter)

        if features:
            sep = QFrame(); sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet("color:#1F242E;background:#1F242E;max-height:1px")
            cl.addWidget(sep)
            sub = QLabel("O que estará disponível:")
            sub.setObjectName("sectionHeader"); sub.setStyleSheet("font-size:12px")
            cl.addWidget(sub)
            for f in features:
                row = QHBoxLayout()
                bullet = QLabel("●"); bullet.setStyleSheet("color:#6366F1;font-size:11px")
                lbl = QLabel(f); lbl.setStyleSheet("color:#8A93A6;font-size:12px")
                lbl.setWordWrap(True)
                row.addWidget(bullet); row.addWidget(lbl, 1)
                cl.addLayout(row)

        root.addWidget(card, alignment=Qt.AlignCenter)
