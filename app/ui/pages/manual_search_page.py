"""Busca Manual — controle total: você define exatamente o que buscar."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services import HuntRequest, hunt_leads
from app.ui.workers import Worker, run_in_thread


class ManualSearchPage(QWidget):
    """Modo cirúrgico: nicho + cidade + qtd. Sem dependência de IA para começar."""
    leads_updated = Signal()

    def __init__(self) -> None:
        super().__init__()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        page = QWidget(); scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 24); root.setSpacing(16)

        intro = QLabel(
            "Use a Busca Manual quando você já sabe exatamente o que procura. "
            "Não precisa de site nem análise de IA — informe os nichos e a região."
        )
        intro.setObjectName("muted"); intro.setWordWrap(True)
        root.addWidget(intro)

        # Card principal
        card = QFrame(); card.setObjectName("sectionCard")
        cl = QVBoxLayout(card); cl.setContentsMargins(20, 18, 20, 18); cl.setSpacing(12)

        ti = QLabel("Critérios da Busca")
        ti.setObjectName("sectionHead"); cl.addWidget(ti)

        cl.addWidget(QLabel("Nichos / palavras-chave (uma por linha ou separados por vírgula)"))
        self.niches_edit = QPlainTextEdit()
        self.niches_edit.setPlaceholderText(
            "Ex.:\n"
            "escritório de advocacia societário\n"
            "contabilidade especializada em e-commerce\n"
            "consultoria tributária para holdings"
        )
        self.niches_edit.setMinimumHeight(120)
        cl.addWidget(self.niches_edit)

        loc = QHBoxLayout(); loc.setSpacing(10)
        self.city_input = QLineEdit(); self.city_input.setPlaceholderText("Cidade — ex: Curitiba")
        self.state_input = QLineEdit(); self.state_input.setPlaceholderText("UF — ex: PR")
        self.country_input = QLineEdit("Brasil")
        self.max_per_niche = QSpinBox(); self.max_per_niche.setRange(5, 100); self.max_per_niche.setValue(25)
        for label, w in [("Cidade", self.city_input), ("Estado", self.state_input),
                         ("País", self.country_input), ("Resultados/nicho", self.max_per_niche)]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label); l.setObjectName("fieldLabel")
            col.addWidget(l); col.addWidget(w)
            loc.addLayout(col, 1)
        cl.addLayout(loc)

        opts = QHBoxLayout()
        self.partners_chk = QCheckBox("Marcar como Parceiros (em vez de Clientes Diretos)")
        self.ai_chk = QCheckBox("Qualificar com IA (gera score, pitch, follow-up)")
        opts.addWidget(self.partners_chk); opts.addWidget(self.ai_chk); opts.addStretch()
        cl.addLayout(opts)

        action = QHBoxLayout(); action.addStretch()
        self.start_btn = QPushButton("🔎  Buscar agora")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(40); self.start_btn.setMinimumWidth(180)
        self.start_btn.clicked.connect(self._start)
        action.addWidget(self.start_btn)
        cl.addLayout(action)

        root.addWidget(card)

        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True); self.log_view.setMinimumHeight(200)
        self.log_view.setPlaceholderText("Resultados aparecem aqui em tempo real…")
        root.addWidget(self.log_view, 1)

    def _parse_niches(self) -> list[str]:
        raw = self.niches_edit.toPlainText()
        items: list[str] = []
        for line in raw.splitlines():
            for piece in line.split(","):
                p = piece.strip()
                if p:
                    items.append(p)
        # dedup mantendo ordem
        return list(dict.fromkeys(items))

    def _start(self) -> None:
        niches = self._parse_niches()
        if not niches:
            QMessageBox.warning(self, "Atenção",
                                "Informe ao menos um nicho/palavra-chave.")
            return
        req = HuntRequest(
            source_input="",
            is_website=False,
            manual_niches=niches,
            city=self.city_input.text().strip(),
            state=self.state_input.text().strip(),
            country=self.country_input.text().strip() or "Brasil",
            max_per_niche=self.max_per_niche.value(),
            use_ai_qualification=self.ai_chk.isChecked(),
            mode="partners" if self.partners_chk.isChecked() else "direct_sale",
        )
        self.start_btn.setEnabled(False)
        self.progress.setValue(0); self.log_view.clear()
        self.log_view.appendPlainText(f"Buscando: {', '.join(niches)}")

        from app.ui.widgets.run_dialog import ProspectionRunDialog
        dlg = ProspectionRunDialog(self, "Busca Manual em andamento", hunt_leads, req)
        dlg.finished.connect(lambda _=0: self._closed(dlg))
        dlg.show(); dlg.start()
        self._dlg = dlg

    def _closed(self, dlg):
        if dlg.error:
            self._fail(dlg.error)
        elif dlg.result is not None:
            self._done(dlg.result)
        else:
            self.start_btn.setEnabled(True)

    def _log(self, m, p):
        self.log_view.appendPlainText(f"[{p:>3}%] {m}"); self.progress.setValue(p)

    def _done(self, result):
        self.start_btn.setEnabled(True)
        self.log_view.appendPlainText(
            f"\n✔ {len(result.leads)} leads salvos. Veja em Leads → Todos os Leads."
        )
        self.leads_updated.emit()

    def _fail(self, msg: str):
        self.start_btn.setEnabled(True)
        self.log_view.appendPlainText(f"\n✖ {msg}")
        QMessageBox.critical(self, "Falha", msg)
