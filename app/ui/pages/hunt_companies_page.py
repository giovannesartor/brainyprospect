"""Caça Empresas — modo avançado focado em SINAIS estratégicos.

Diferente da Busca Inteligente, aqui o operador escolhe combinações específicas
de sinais comerciais e a região é mais flexível (multi-cidade).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
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


# Sinais avançados — cada um vira um modificador de busca
SIGNALS = [
    ("growth",      "🚀", "Crescimento Acelerado",
     "Hiring agressivo, abertura de filiais, expansão regional"),
    ("capital",     "💰", "Captação Recente",
     "Receberam aporte, série A/B/C, IPO ou private equity"),
    ("ma",          "🤝", "M&A / Holding",
     "Holdings familiares, fusões, aquisições, sucessão"),
    ("franchise",   "🏪", "Franquias / Multi-unidades",
     "Modelo de franquia, várias unidades, expansão"),
    ("high_ticket", "💎", "Alto Ticket / Premium",
     "Empresas premium, ticket médio elevado, B2B sofisticado"),
    ("export",      "🌎", "Exportação / Internacional",
     "Atuam fora do Brasil, exportadores, multinacionais"),
    ("tech",        "🧠", "Tech / SaaS / Startup",
     "Startups, scale-ups, SaaS, produtos digitais"),
    ("traditional", "🏛", "Consolidadas (10+ anos)",
     "Empresas tradicionais, bem estabelecidas, marca reconhecida"),
    ("ecom",        "🛒", "E-commerce / D2C",
     "Lojas online, marketplaces, direct-to-consumer"),
    ("agro",        "🌾", "Agronegócio",
     "Produtores rurais, cooperativas, agroindústria"),
    ("health",      "🏥", "Saúde / Clínicas",
     "Clínicas, hospitais, redes médicas, healthtech"),
    ("legal",       "⚖️", "Jurídico / Compliance",
     "Escritórios de advocacia, compliance, regulatório"),
]

PRESETS = {
    "Custom": [],
    "🦄 Startups bem capitalizadas": ["tech", "capital", "growth"],
    "🏛 Holdings & Sucessão": ["ma", "high_ticket"],
    "🛒 E-commerce em escala": ["ecom", "growth"],
    "🌎 Exportadores premium": ["export", "high_ticket"],
    "🏪 Redes em expansão": ["franchise", "growth"],
    "⚖️ Jurídico estratégico": ["legal", "high_ticket"],
    "🏥 Healthtech / Clínicas": ["health", "tech"],
}


class _SignalCard(QFrame):
    toggled = Signal(bool)

    def __init__(self, key: str, emoji: str, label: str, desc: str) -> None:
        super().__init__()
        self.key = key; self._on = False
        self.setObjectName("card"); self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(96)
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 12, 14, 12); lay.setSpacing(4)
        top = QHBoxLayout()
        ico = QLabel(emoji); ico.setStyleSheet("font-size:18px")
        title = QLabel(label); title.setStyleSheet("font-weight:700;font-size:12px")
        top.addWidget(ico); top.addWidget(title); top.addStretch()
        self.dot = QLabel("○"); self.dot.setStyleSheet("font-size:14px;color:#6B7280")
        top.addWidget(self.dot)
        lay.addLayout(top)
        d = QLabel(desc); d.setWordWrap(True)
        d.setStyleSheet("color:#8A93A6;font-size:11px;line-height:14px")
        lay.addWidget(d); lay.addStretch()
        self._restyle()

    def setChecked(self, v: bool) -> None:
        if self._on != v:
            self._on = v; self._restyle(); self.toggled.emit(v)

    def isChecked(self) -> bool:
        return self._on

    def mousePressEvent(self, ev) -> None:
        self.setChecked(not self._on); super().mousePressEvent(ev)

    def _restyle(self) -> None:
        from app.ui.theme import colors
        c = colors()
        if self._on:
            self.setStyleSheet(
                f"QFrame#card{{background:{c['selected']};"
                f"border:2px solid {c['accent']};border-radius:12px}}"
            )
            self.dot.setText("●"); self.dot.setStyleSheet(f"color:{c['accent']};font-size:14px")
        else:
            self.setStyleSheet(
                f"QFrame#card{{background:{c['panel']};"
                f"border:1px solid {c['border']};border-radius:12px}}"
            )
            self.dot.setText("○"); self.dot.setStyleSheet(f"color:{c['text_mute']};font-size:14px")


class HuntCompaniesPage(QWidget):
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
            "🎯  <b>Caça Empresas</b> — modo avançado para alvejar empresas com "
            "sinais estratégicos específicos. Combine sinais para refinar a caça."
        )
        intro.setObjectName("intro"); intro.setWordWrap(True)
        root.addWidget(intro)

        # Preset card
        preset_card = QFrame(); preset_card.setObjectName("sectionCard")
        pl = QVBoxLayout(preset_card); pl.setContentsMargins(20, 14, 20, 16); pl.setSpacing(8)
        pl.addWidget(self._mk_head("⚡  Presets de Caça",
                                    "Combinações pré-definidas dos melhores sinais."))
        self.preset_combo = QComboBox()
        for k in PRESETS.keys():
            self.preset_combo.addItem(k)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        pl.addWidget(self.preset_combo)
        root.addWidget(preset_card)

        # Sinais
        signals_card = QFrame(); signals_card.setObjectName("sectionCard")
        sl = QVBoxLayout(signals_card); sl.setContentsMargins(20, 14, 20, 16); sl.setSpacing(10)
        sl.addWidget(self._mk_head("🎯  Sinais Estratégicos",
                                    "Selecione múltiplos. Quanto mais sinais, mais específica a busca."))
        grid = QGridLayout(); grid.setSpacing(10)
        self.cards: dict[str, _SignalCard] = {}
        for i, (k, e, lbl, d) in enumerate(SIGNALS):
            card = _SignalCard(k, e, lbl, d)
            self.cards[k] = card
            grid.addWidget(card, i // 4, i % 4)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        sl.addLayout(grid)
        root.addWidget(signals_card)

        # Nichos âncora + região
        anchor_card = QFrame(); anchor_card.setObjectName("sectionCard")
        al = QVBoxLayout(anchor_card); al.setContentsMargins(20, 14, 20, 16); al.setSpacing(10)
        al.addWidget(self._mk_head("📍  Âncora & Região",
                                    "Defina nichos âncora e onde caçar."))
        al.addWidget(QLabel("Nichos âncora (separados por vírgula)"))
        self.niches = QLineEdit()
        self.niches.setPlaceholderText("Ex: contabilidade, fintech, indústria, e-commerce")
        al.addWidget(self.niches)

        al.addWidget(QLabel("Cidades-alvo (uma por linha)"))
        self.cities_edit = QPlainTextEdit()
        self.cities_edit.setPlaceholderText("São Paulo\nRio de Janeiro\nBelo Horizonte")
        self.cities_edit.setMaximumHeight(90)
        al.addWidget(self.cities_edit)

        row = QHBoxLayout()
        self.state_input = QLineEdit(); self.state_input.setPlaceholderText("UF padrão (opcional)")
        self.country_input = QLineEdit("Brasil")
        self.max_per_niche = QSpinBox(); self.max_per_niche.setRange(10, 80); self.max_per_niche.setValue(20)
        for label, w in [("UF padrão", self.state_input),
                         ("País", self.country_input),
                         ("Resultados/combinação", self.max_per_niche)]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label); l.setObjectName("fieldLabel")
            col.addWidget(l); col.addWidget(w)
            row.addLayout(col, 1)
        al.addLayout(row)

        opts = QHBoxLayout()
        self.partners_chk = QCheckBox("Marcar como Parceiros")
        self.ai_chk = QCheckBox("Qualificar com IA"); self.ai_chk.setChecked(True)
        opts.addWidget(self.partners_chk); opts.addWidget(self.ai_chk); opts.addStretch()
        al.addLayout(opts)

        action = QHBoxLayout(); action.addStretch()
        self.start_btn = QPushButton("🎯  Iniciar Caça")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumWidth(200); self.start_btn.setMinimumHeight(42)
        self.start_btn.clicked.connect(self._start)
        action.addWidget(self.start_btn)
        al.addLayout(action)

        root.addWidget(anchor_card)

        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True); self.log_view.setMinimumHeight(180)
        self.log_view.setPlaceholderText("Logs da caça aparecem aqui…")
        root.addWidget(self.log_view, 1)

        from app.ui.theme import on_theme_changed
        on_theme_changed(lambda _t: [c._restyle() for c in self.cards.values()])

    def _mk_head(self, title: str, sub: str = "") -> QWidget:
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(2)
        t = QLabel(title); t.setObjectName("sectionHead"); l.addWidget(t)
        if sub:
            s = QLabel(sub); s.setObjectName("sectionSub"); s.setWordWrap(True); l.addWidget(s)
        return w

    def _apply_preset(self, name: str) -> None:
        keys = PRESETS.get(name, [])
        for k, c in self.cards.items():
            c.setChecked(k in keys)

    def _modifiers(self) -> list[str]:
        mp = {
            "growth": "em crescimento contratando",
            "capital": "captação investimento aporte",
            "ma": "holding aquisição M&A",
            "franchise": "franquia expansão multi-unidade",
            "high_ticket": "premium alto padrão",
            "export": "exportação internacional",
            "tech": "tecnologia SaaS startup",
            "traditional": "tradicional consolidada",
            "ecom": "e-commerce loja online",
            "agro": "agronegócio agro",
            "health": "saúde clínica hospital",
            "legal": "advocacia jurídico compliance",
        }
        return [mp[k] for k, c in self.cards.items() if c.isChecked() and k in mp]

    def _start(self) -> None:
        anchors = [n.strip() for n in self.niches.text().split(",") if n.strip()]
        if not anchors:
            QMessageBox.warning(self, "Atenção",
                                "Informe pelo menos um nicho âncora.")
            return
        cities = [c.strip() for c in self.cities_edit.toPlainText().splitlines() if c.strip()]
        if not cities:
            cities = [""]  # rodar uma vez sem cidade

        modifiers = self._modifiers()
        # combina cada anchor x modificadores
        combined_niches: list[str] = []
        for a in anchors:
            if modifiers:
                combined_niches.append(f"{a} {' '.join(modifiers)}")
            else:
                combined_niches.append(a)

        self.start_btn.setEnabled(False); self.progress.setValue(0)
        self.log_view.clear()
        self.log_view.appendPlainText(
            f"🎯 Caça iniciada — {len(combined_niches)} nicho(s) × {len(cities)} cidade(s) "
            f"= até {len(combined_niches) * len(cities)} buscas."
        )
        self._queue = [(c, combined_niches) for c in cities]
        self._results_total = 0
        self._run_next()

    def _run_next(self) -> None:
        if not self._queue:
            self.start_btn.setEnabled(True)
            self.log_view.appendPlainText(
                f"\n✔ Caça finalizada. Total: {self._results_total} leads salvos."
            )
            self.leads_updated.emit()
            return
        city, niches = self._queue.pop(0)
        self.log_view.appendPlainText(f"\n→ Caçando em '{city or 'sem cidade'}'…")
        req = HuntRequest(
            source_input="", is_website=False,
            manual_niches=niches,
            city=city, state=self.state_input.text().strip(),
            country=self.country_input.text().strip() or "Brasil",
            max_per_niche=self.max_per_niche.value(),
            use_ai_qualification=self.ai_chk.isChecked(),
            mode="partners" if self.partners_chk.isChecked() else "direct_sale",
        )
        worker = Worker(hunt_leads, req, with_progress=True)
        run_in_thread(self, worker,
                      on_finished=self._batch_done,
                      on_failed=self._batch_failed,
                      on_progress=self._log)

    def _log(self, m, p):
        self.log_view.appendPlainText(f"   [{p:>3}%] {m}")
        self.progress.setValue(p)

    def _batch_done(self, result):
        self._results_total += len(result.leads)
        self.log_view.appendPlainText(
            f"   ✔ {len(result.leads)} leads nesta cidade."
        )
        self._run_next()

    def _batch_failed(self, msg: str):
        self.log_view.appendPlainText(f"   ✖ {msg}")
        self._run_next()  # continua com a próxima cidade
