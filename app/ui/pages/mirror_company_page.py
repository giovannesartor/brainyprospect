"""Empresa Espelho — encontra empresas similares ao seu cliente ideal.

Fluxo:
1. Usuário informa o site de UM cliente ideal já existente
2. IA analisa o site e extrai segmento + características
3. Sistema busca empresas com o MESMO perfil (lookalikes)
"""
from __future__ import annotations

from PySide6.QtCore import Signal
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


class MirrorCompanyPage(QWidget):
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
            "🪞  <b>Empresa Espelho</b> — informe o site de um cliente ideal seu "
            "(ou de um concorrente). A IA extrai o ADN do negócio e busca empresas "
            "com o mesmo perfil em qualquer região do Brasil."
        )
        intro.setObjectName("intro")
        intro.setWordWrap(True)
        root.addWidget(intro)

        card = QFrame(); card.setObjectName("sectionCard")
        cl = QVBoxLayout(card); cl.setContentsMargins(20, 18, 20, 18); cl.setSpacing(12)

        head = QLabel("Site da Empresa de Referência"); head.setObjectName("sectionHead")
        cl.addWidget(head)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://meucliente.com.br")
        self.url_input.setMinimumHeight(42)
        cl.addWidget(self.url_input)

        sub = QLabel(
            "Dica: use a empresa que mais te dá lucro hoje. "
            "Quanto mais conteúdo no site, melhor a análise."
        )
        sub.setObjectName("mutedSmall"); sub.setWordWrap(True)
        cl.addWidget(sub)

        # filtros adicionais
        loc = QHBoxLayout(); loc.setSpacing(10)
        self.city = QLineEdit(); self.city.setPlaceholderText("Cidade-alvo (opcional)")
        self.state = QLineEdit(); self.state.setPlaceholderText("UF (opcional)")
        self.max_per_niche = QSpinBox(); self.max_per_niche.setRange(10, 80); self.max_per_niche.setValue(25)
        for label, w in [("Cidade", self.city), ("Estado", self.state),
                         ("Lookalikes/segmento", self.max_per_niche)]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label); l.setObjectName("fieldLabel")
            col.addWidget(l); col.addWidget(w)
            loc.addLayout(col, 1)
        cl.addLayout(loc)

        opts = QHBoxLayout()
        self.qual_chk = QCheckBox("Qualificar com IA"); self.qual_chk.setChecked(True)
        self.same_size_chk = QCheckBox("Priorizar empresas de PORTE SIMILAR")
        self.same_size_chk.setChecked(True)
        opts.addWidget(self.qual_chk); opts.addWidget(self.same_size_chk); opts.addStretch()
        cl.addLayout(opts)

        action = QHBoxLayout(); action.addStretch()
        self.start_btn = QPushButton("🔍  Encontrar Lookalikes")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumWidth(220); self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start)
        action.addWidget(self.start_btn)
        cl.addLayout(action)

        root.addWidget(card)

        # análise de DNA
        self.dna_card = QFrame(); self.dna_card.setObjectName("sectionCard")
        dl = QVBoxLayout(self.dna_card); dl.setContentsMargins(20, 16, 20, 18)
        dl.addWidget(QLabel("🧬  ADN da Empresa de Referência"))
        self.dna_text = QPlainTextEdit()
        self.dna_text.setReadOnly(True); self.dna_text.setMinimumHeight(140)
        self.dna_text.setPlaceholderText("Após a análise, o perfil aparecerá aqui.")
        dl.addWidget(self.dna_text)
        root.addWidget(self.dna_card)

        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True); self.log_view.setMinimumHeight(180)
        root.addWidget(self.log_view, 1)

    def _start(self) -> None:
        url = self.url_input.text().strip()
        if not url.startswith(("http://", "https://", "www.")):
            QMessageBox.warning(self, "URL inválida",
                                "Informe um site começando com http(s)://")
            return
        if url.startswith("www."):
            url = "https://" + url

        req = HuntRequest(
            source_input=url, is_website=True,
            manual_niches=[],  # vamos deixar a IA decidir os lookalikes
            city=self.city.text().strip(),
            state=self.state.text().strip(),
            country="Brasil",
            max_per_niche=self.max_per_niche.value(),
            use_ai_qualification=self.qual_chk.isChecked(),
            mode="direct_sale",  # lookalike sempre é cliente direto
        )

        self.start_btn.setEnabled(False); self.progress.setValue(0)
        self.log_view.clear(); self.dna_text.clear()
        self.log_view.appendPlainText(f"Analisando ADN de {url}…")

        from app.ui.widgets.run_dialog import ProspectionRunDialog
        dlg = ProspectionRunDialog(self, "Encontrando lookalikes", hunt_leads, req)
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
        icp = result.icp
        if icp.business_type:
            dna = (
                f"📌 Tipo: {icp.business_type}\n"
                f"📝 Resumo: {icp.summary}\n\n"
                f"🎯 Clientes-alvo similares:\n  • "
                + "\n  • ".join(icp.direct_clients or icp.ideal_clients or ["—"])
                + "\n\n🔑 Palavras-chave de busca:\n  • "
                + "\n  • ".join(icp.direct_keywords or icp.keywords or ["—"])
            )
            self.dna_text.setPlainText(dna)
        self.log_view.appendPlainText(
            f"\n✔ {len(result.leads)} empresas similares encontradas. "
            "Veja em Leads → Todos."
        )
        self.leads_updated.emit()

    def _fail(self, msg: str):
        self.start_btn.setEnabled(True)
        self.log_view.appendPlainText(f"\n✖ {msg}")
        QMessageBox.critical(self, "Falha", msg)
