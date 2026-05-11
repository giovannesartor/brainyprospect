"""Busca Inteligente — formulário largo com critérios em cards visuais."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

from app.services import (
    AnalysisResult,
    HuntRequest,
    analyze_business,
    generate_product_details,
    hunt_leads,
)
from app.services.source_health import SourceStatus, check_all
from app.ui.theme import colors, on_theme_changed
from app.ui.workers import Worker, run_in_thread


# (key, emoji, label, description)
HUNT_CRITERIA = [
    ("growth",       "🚀", "Em Crescimento",
     "Empresas escalando, contratando, abrindo filiais"),
    ("capital",      "💰", "Captação / Investimento",
     "Receberam aporte, série A/B, IPO, M&A"),
    ("franchise",    "🏪", "Franquias / Expansão",
     "Modelo de franchising e abertura de unidades"),
    ("ma",           "🤝", "M&A / Holding",
     "Holdings familiares, aquisições, fusões"),
    ("high_ticket",  "💎", "Alto Ticket",
     "Empresas premium com ticket médio elevado"),
    ("tech",         "🧠", "Tech / Inovação",
     "Startups, SaaS, scale-ups com stack moderna"),
    ("traditional",  "🏛", "Negócios Tradicionais",
     "Empresas consolidadas há +10 anos no mercado"),
    ("export",       "🌎", "Exportação / Global",
     "Empresas que exportam ou atuam fora do país"),
]


def _segmented_button(text: str, checked: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("seg")
    b.setCheckable(True)
    b.setChecked(checked)
    b.setCursor(Qt.PointingHandCursor)
    b.setMinimumHeight(40)
    return b


class _CriterionCard(QFrame):
    """Card clicável (grande) que funciona como toggle."""
    toggled = Signal(bool)

    def __init__(self, key: str, emoji: str, label: str, desc: str) -> None:
        super().__init__()
        self.key = key
        self._checked = False
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(98)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        top = QHBoxLayout(); top.setSpacing(8)
        ico = QLabel(emoji); ico.setStyleSheet("font-size:20px")
        title = QLabel(label)
        title.setStyleSheet("font-weight:700;font-size:13px")
        top.addWidget(ico); top.addWidget(title); top.addStretch()
        self._dot = QLabel("○")
        self._dot.setStyleSheet("font-size:16px;color:#6B7280")
        top.addWidget(self._dot)
        lay.addLayout(top)

        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("color:#8A93A6;font-size:11px;line-height:14px")
        lay.addWidget(d)
        lay.addStretch()
        self._restyle()

    def mousePressEvent(self, ev) -> None:
        self._checked = not self._checked
        self._restyle()
        self.toggled.emit(self._checked)
        super().mousePressEvent(ev)

    def isChecked(self) -> bool:
        return self._checked

    def _restyle(self) -> None:
        c = colors()
        if self._checked:
            self.setStyleSheet(
                f"QFrame#card{{background:{c['selected']};"
                f"border:2px solid {c['accent']};border-radius:12px}}"
            )
            self._dot.setText("●")
            self._dot.setStyleSheet(f"font-size:16px;color:{c['accent']}")
        else:
            self.setStyleSheet(
                f"QFrame#card{{background:{c['panel']};"
                f"border:1px solid {c['border']};border-radius:12px}}"
            )
            self._dot.setText("○")
            self._dot.setStyleSheet(f"font-size:16px;color:{c['text_mute']}")


class _ProductCard(QFrame):
    """Card de produto detectado pela IA, com toggle Direto/Ambos/Parceiros.

    Expandível: revela editores de keywords/clientes/parceiros para edição manual
    antes da busca.
    """

    removed = Signal(object)  # emite self quando usuário remove o card

    def __init__(self, product: dict) -> None:
        super().__init__()
        self.product = product
        self.setObjectName("productCard")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QHBoxLayout(); head.setSpacing(8)
        self.include_chk = QCheckBox()
        self.include_chk.setChecked(True)
        head.addWidget(self.include_chk)
        title = QLabel(product.get("name", ""))
        title.setStyleSheet("font-weight:700;font-size:14px")
        head.addWidget(title)
        head.addStretch()
        rec = (product.get("recommended_mode") or "").strip()
        if rec:
            tag = QLabel("💡 IA sugere: "
                         + {"direct_sale": "Direto",
                            "partners": "Parceiros",
                            "both": "Ambos"}.get(rec, rec))
            tag.setStyleSheet("color:#8A93A6;font-size:11px")
            head.addWidget(tag)

        self.expand_btn = QPushButton("✏️  Editar")
        self.expand_btn.setObjectName("ghost")
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setCheckable(True)
        self.expand_btn.toggled.connect(self._toggle_expand)
        head.addWidget(self.expand_btn)

        self.remove_btn = QPushButton("🗑")
        self.remove_btn.setObjectName("ghost")
        self.remove_btn.setFixedWidth(32)
        self.remove_btn.setToolTip("Remover este produto")
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))
        head.addWidget(self.remove_btn)

        lay.addLayout(head)

        desc = (product.get("description") or "").strip()
        if desc:
            d = QLabel(desc); d.setWordWrap(True)
            d.setStyleSheet("color:#8A93A6;font-size:11px")
            lay.addWidget(d)

        # Toggle de modo por produto
        mode_row = QHBoxLayout(); mode_row.setSpacing(6)
        self.btn_direct = _segmented_button("🎯  Direto", checked=True)
        self.btn_both = _segmented_button("⇄  Ambos")
        self.btn_partners = _segmented_button("🤝  Parceiros")
        for b in (self.btn_direct, self.btn_both, self.btn_partners):
            b.setMinimumHeight(32)
            mode_row.addWidget(b, 1)
        self._mode_group = QButtonGroup(self); self._mode_group.setExclusive(True)
        for b in (self.btn_direct, self.btn_both, self.btn_partners):
            self._mode_group.addButton(b)
        # Pré-seleciona o modo recomendado pela IA, se houver
        if rec == "partners":
            self.btn_direct.setChecked(False); self.btn_partners.setChecked(True)
        elif rec == "both":
            self.btn_direct.setChecked(False); self.btn_both.setChecked(True)
        lay.addLayout(mode_row)

        # Resumo de keywords detectadas
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color:#6B7280;font-size:10px")
        lay.addWidget(self.info_label)
        self._update_info_label()

        # ---- Painel de edição (oculto por padrão) ----
        self.edit_panel = QFrame()
        self.edit_panel.setObjectName("editPanel")
        ep = QVBoxLayout(self.edit_panel)
        ep.setContentsMargins(0, 8, 0, 0)
        ep.setSpacing(8)

        ep.addWidget(self._editor_label("🎯 Termos de busca — CLIENTES DIRETOS",
                                       "Um por linha. Estes termos viram queries no Google Maps/Bing/DDG."))
        self.direct_kw_edit = QPlainTextEdit(
            "\n".join(product.get("direct_keywords") or [])
        )
        self.direct_kw_edit.setMaximumHeight(110)
        ep.addWidget(self.direct_kw_edit)

        ep.addWidget(self._editor_label("🤝 Termos de busca — PARCEIROS / INDICADORES",
                                       "Um por linha. Quem atende o mesmo público e pode INDICAR."))
        self.partner_kw_edit = QPlainTextEdit(
            "\n".join(product.get("partner_keywords") or [])
        )
        self.partner_kw_edit.setMaximumHeight(110)
        ep.addWidget(self.partner_kw_edit)

        # Sincroniza alterações de volta para self.product no foco perdido
        self.direct_kw_edit.textChanged.connect(self._sync_keywords)
        self.partner_kw_edit.textChanged.connect(self._sync_keywords)

        self.edit_panel.setVisible(False)
        lay.addWidget(self.edit_panel)

    @staticmethod
    def _editor_label(title: str, hint: str) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(2)
        a = QLabel(title); a.setObjectName("sectionHeader"); a.setStyleSheet("font-size:11px")
        b = QLabel(hint); b.setStyleSheet("font-size:10px;color:#8A93A6")
        v.addWidget(a); v.addWidget(b)
        return w

    def _toggle_expand(self, on: bool) -> None:
        self.edit_panel.setVisible(on)
        self.expand_btn.setText("▲  Recolher" if on else "✏️  Editar")

    def _sync_keywords(self) -> None:
        self.product["direct_keywords"] = [
            x.strip() for x in self.direct_kw_edit.toPlainText().splitlines() if x.strip()
        ]
        self.product["partner_keywords"] = [
            x.strip() for x in self.partner_kw_edit.toPlainText().splitlines() if x.strip()
        ]
        self._update_info_label()

    def _update_info_label(self) -> None:
        dk = len(self.product.get("direct_keywords") or [])
        pk = len(self.product.get("partner_keywords") or [])
        self.info_label.setText(
            f"🎯 {dk} termos diretos  ·  🤝 {pk} termos de parceiros"
        )

    def is_selected(self) -> bool:
        return self.include_chk.isChecked()

    def selected_mode(self) -> str:
        if self.btn_partners.isChecked():
            return "partners"
        if self.btn_both.isChecked():
            return "both"
        return "direct_sale"

    def to_payload(self) -> dict:
        # garante sincronização caso usuário não tenha tirado o foco
        self._sync_keywords()
        return {
            "name": self.product.get("name", ""),
            "mode": self.selected_mode(),
            "direct_keywords": self.product.get("direct_keywords") or [],
            "direct_clients": self.product.get("direct_clients") or [],
            "partner_keywords": self.product.get("partner_keywords") or [],
            "partner_segments": self.product.get("partner_segments") or [],
        }


class SearchPage(QWidget):
    leads_updated = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._analysis: AnalysisResult | None = None
        self._product_cards: list[_ProductCard] = []

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        page = QWidget()
        scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        # ---------------- 0) BARRA DE SAÚDE DAS FONTES
        self.health_bar = QFrame()
        self.health_bar.setObjectName("healthBar")
        hb_lay = QHBoxLayout(self.health_bar)
        hb_lay.setContentsMargins(12, 6, 12, 6)
        hb_lay.setSpacing(14)
        hb_lay.addWidget(QLabel("📡 Fontes:"))
        self.health_dots: dict[str, QLabel] = {}
        for name in ("IA", "Bing", "DuckDuckGo", "Google Maps"):
            row = QHBoxLayout(); row.setSpacing(4)
            dot = QLabel("⚪"); dot.setStyleSheet("font-size:13px")
            self.health_dots[name] = dot
            lbl = QLabel(name); lbl.setObjectName("muted"); lbl.setStyleSheet("font-size:11px")
            w = QWidget(); w.setLayout(row)
            row.addWidget(dot); row.addWidget(lbl)
            hb_lay.addWidget(w)
        hb_lay.addStretch()
        self.health_refresh_btn = QPushButton("🔄")
        self.health_refresh_btn.setObjectName("ghost")
        self.health_refresh_btn.setFixedWidth(32)
        self.health_refresh_btn.setToolTip("Re-checar fontes")
        self.health_refresh_btn.clicked.connect(
            lambda: self._check_health(include_playwright=True)
        )
        hb_lay.addWidget(self.health_refresh_btn)
        root.addWidget(self.health_bar)
        # checa em background ao abrir
        QTimer.singleShot(300, lambda: self._check_health(include_playwright=False))

        # ---------------- 1) ENTRADA
        sec1 = self._section("1. O que você vende?",
                             "Cole o site da sua empresa OU descreva seu negócio. "
                             "A IA extrai seu ICP automaticamente.")
        s1_box = QVBoxLayout(); s1_box.setSpacing(10)
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText(
            "https://meusite.com.br  ou  ‘Vendo software de gestão para clínicas’"
        )
        self.source_input.setMinimumHeight(42)
        s1_box.addWidget(self.source_input)

        self.is_website_chk = QCheckBox(
            "Tratar como SITE (a IA fará scraping e análise)"
        )
        self.is_website_chk.setChecked(True)
        s1_box.addWidget(self.is_website_chk)

        # Botão opcional: analisar antes de buscar (descobre produtos)
        analyze_row = QHBoxLayout()
        self.analyze_btn = QPushButton("🔍  Analisar site e detectar produtos")
        self.analyze_btn.setObjectName("ghost")
        self.analyze_btn.setMinimumHeight(36)
        self.analyze_btn.clicked.connect(lambda: self._analyze_site(force=False))
        analyze_row.addWidget(self.analyze_btn)
        self.reanalyze_btn = QPushButton("♻️  Re-analisar")
        self.reanalyze_btn.setObjectName("ghost")
        self.reanalyze_btn.setMinimumHeight(36)
        self.reanalyze_btn.setToolTip("Ignora o cache e refaz a análise do zero")
        self.reanalyze_btn.clicked.connect(lambda: self._analyze_site(force=True))
        analyze_row.addWidget(self.reanalyze_btn)
        analyze_row.addStretch()
        self.analyze_status = QLabel("")
        self.analyze_status.setStyleSheet("color:#8A93A6;font-size:11px")
        analyze_row.addWidget(self.analyze_status)
        s1_box.addLayout(analyze_row)

        sec1["body"].addLayout(s1_box)
        root.addWidget(sec1["card"])

        # ---------------- 1.5) PRODUTOS DETECTADOS (aparece após análise)
        self.products_section = self._section(
            "📦 Produtos detectados pela IA",
            "Marque quais você quer prospectar e escolha, para cada um, se busca "
            "compradores diretos, parceiros que indicam, ou ambos.",
        )
        self.products_container = QVBoxLayout()
        self.products_container.setSpacing(8)
        self.products_section["body"].addLayout(self.products_container)
        self.products_empty = QLabel(
            "Nenhum produto detectado ainda. Clique em “Analisar site” acima."
        )
        self.products_empty.setStyleSheet("color:#8A93A6;font-size:11px;padding:8px")
        self.products_container.addWidget(self.products_empty)

        # Botão adicionar produto manual
        self.add_product_btn = QPushButton("➕  Adicionar produto manualmente")
        self.add_product_btn.setObjectName("ghost")
        self.add_product_btn.setMinimumHeight(36)
        self.add_product_btn.clicked.connect(self._add_product_manually)
        self.products_section["body"].addWidget(self.add_product_btn)
        self.products_section["card"].setVisible(False)
        root.addWidget(self.products_section["card"])

        # ---------------- 2) ESTRATÉGIA COMERCIAL
        sec2 = self._section("2. Estratégia Comercial",
                             "Como você quer prospectar?")
        strat_row = QHBoxLayout(); strat_row.setSpacing(10)
        self.btn_direct = _segmented_button("🎯  Venda Direta", checked=True)
        self.btn_both = _segmented_button("⇄  Ambos")
        self.btn_partners = _segmented_button("🤝  Parceiros / Indicadores")
        self._strat_group = QButtonGroup(self); self._strat_group.setExclusive(True)
        for b in (self.btn_direct, self.btn_both, self.btn_partners):
            strat_row.addWidget(b, 1)
            self._strat_group.addButton(b)
        sec2["body"].addLayout(strat_row)

        self.strat_hint = QLabel(
            "🎯 Buscar clientes finais com sinais reais de demanda."
        )
        self.strat_hint.setStyleSheet("color:#6B7280;font-size:11px;padding-top:4px")
        self.strat_hint.setWordWrap(True)
        sec2["body"].addWidget(self.strat_hint)
        for b, m in [(self.btn_direct, "direct_sale"),
                     (self.btn_both, "both"),
                     (self.btn_partners, "partners")]:
            b.clicked.connect(lambda _=False, mm=m: self._set_strategy(mm))
        root.addWidget(sec2["card"])

        # ---------------- 3) CAÇA EMPRESAS — CRITÉRIOS EM CARDS
        sec3 = self._section(
            "3. 🎯 Caça Empresas — Sinais Estratégicos",
            "Selecione os perfis de empresa que você quer atacar. "
            "A IA combinará isso aos nichos detectados para gerar buscas direcionadas."
        )
        grid = QGridLayout()
        grid.setSpacing(10)
        self.criteria_cards: dict[str, _CriterionCard] = {}
        for i, (key, emoji, label, desc) in enumerate(HUNT_CRITERIA):
            card = _CriterionCard(key, emoji, label, desc)
            self.criteria_cards[key] = card
            grid.addWidget(card, i // 4, i % 4)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        sec3["body"].addLayout(grid)
        root.addWidget(sec3["card"])

        # ---------------- 4) NICHOS MANUAIS + LOCAL
        sec4 = self._section("4. Refinamento (opcional)",
                             "Sobrescreva nichos detectados ou limite a região.")
        s4_box = QVBoxLayout()
        self.niches_input = QLineEdit()
        self.niches_input.setPlaceholderText(
            "Nichos manuais separados por vírgula. Ex: contabilidade, advogado societário"
        )
        s4_box.addWidget(QLabel("Nichos manuais"))
        s4_box.addWidget(self.niches_input)

        loc_row = QHBoxLayout(); loc_row.setSpacing(10)
        self.city_input = QLineEdit(); self.city_input.setPlaceholderText("São Paulo")
        self.state_input = QLineEdit(); self.state_input.setPlaceholderText("SP")
        self.country_input = QLineEdit("Brasil")
        self.max_per_niche = QSpinBox()
        self.max_per_niche.setRange(5, 100); self.max_per_niche.setValue(15)

        for label, w in [("Cidade", self.city_input),
                         ("Estado", self.state_input),
                         ("País", self.country_input),
                         ("Resultados/nicho", self.max_per_niche)]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label); l.setObjectName("fieldLabel")
            col.addWidget(l); col.addWidget(w)
            loc_row.addLayout(col, 1)
        s4_box.addLayout(loc_row)

        self.use_ai_chk = QCheckBox(
            "Qualificar com IA (recomendado — gera score, pitch, follow-up)"
        )
        self.use_ai_chk.setChecked(True)
        s4_box.addWidget(self.use_ai_chk)
        sec4["body"].addLayout(s4_box)
        root.addWidget(sec4["card"])

        # ---------------- AÇÃO
        action_row = QHBoxLayout()
        action_row.addStretch()
        self.start_btn = QPushButton("🚀  Iniciar Prospecção")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumWidth(220)
        self.start_btn.setMinimumHeight(44)
        self.start_btn.clicked.connect(self._start)
        action_row.addWidget(self.start_btn)
        root.addLayout(action_row)

        # progresso
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Aguardando início da prospecção…")
        self.log_view.setMinimumHeight(220)
        root.addWidget(self.log_view, 1)

        on_theme_changed(lambda _t: [c._restyle() for c in self.criteria_cards.values()])

    # ---------------------------------------------------------------- helpers
    def _section(self, title: str, sub: str = "") -> dict:
        card = QFrame(); card.setObjectName("sectionCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 18); cl.setSpacing(10)
        head = QVBoxLayout(); head.setSpacing(2)
        t = QLabel(title); t.setObjectName("sectionHead")
        head.addWidget(t)
        if sub:
            s = QLabel(sub); s.setObjectName("sectionSub"); s.setWordWrap(True)
            head.addWidget(s)
        cl.addLayout(head)
        body = QVBoxLayout(); body.setSpacing(10)
        cl.addLayout(body)
        return {"card": card, "body": body}

    def _set_strategy(self, mode: str) -> None:
        hints = {
            "direct_sale": "🎯 Buscar clientes finais com sinais reais de demanda.",
            "partners": "🤝 Buscar canais multiplicadores (contadores, advogados, "
                        "consultorias) que possam indicar clientes recorrentes.",
            "both": "⇄ Roda ambas estratégias em paralelo e classifica cada lead.",
        }
        self.strat_hint.setText(hints.get(mode, ""))
        self._strategy = mode

    def _strategy_value(self) -> str:
        if self.btn_partners.isChecked():
            return "partners"
        if self.btn_both.isChecked():
            return "both"
        return "direct_sale"

    def highlight_recommendation(self, mode: str) -> None:
        """Marca visualmente o modo recomendado pela IA."""
        if mode not in ("direct_sale", "partners"):
            return
        label = "Parceiros" if mode == "partners" else "Venda Direta"
        self.strat_hint.setText(f"💡 IA sugere começar por: {label}.\n" + self.strat_hint.text())

    # ---------------------------------------------------------------- run
    def _selected_criteria(self) -> list[str]:
        modifiers = []
        for k, card in self.criteria_cards.items():
            if not card.isChecked():
                continue
            modifiers.append({
                "growth": "em crescimento",
                "capital": "captação investimento",
                "franchise": "franquia expansão",
                "ma": "holding aquisição M&A",
                "high_ticket": "premium alto ticket",
                "tech": "startup tecnologia SaaS",
                "traditional": "tradicional consolidada",
                "export": "exportação internacional",
            }.get(k, k))
        return modifiers

    def _start(self) -> None:
        source = self.source_input.text().strip()
        manual = [n.strip() for n in self.niches_input.text().split(",") if n.strip()]
        if not source and not manual:
            QMessageBox.warning(self, "Atenção",
                                "Informe um site, descrição OU pelo menos um nicho.")
            return

        modifiers = self._selected_criteria()
        if modifiers and manual:
            manual = [f"{n} {' '.join(modifiers)}".strip() for n in manual]

        is_url = source.startswith(("http://", "https://", "www."))
        selected_products = [
            c.to_payload() for c in self._product_cards if c.is_selected()
        ]
        preloaded_icp = None
        preloaded_summary = ""
        if self._analysis is not None:
            preloaded_icp = self._analysis.icp.model_dump()
            preloaded_summary = self._analysis.business_summary

        req = HuntRequest(
            source_input=source,
            is_website=self.is_website_chk.isChecked() and is_url,
            manual_niches=manual,
            city=self.city_input.text().strip(),
            state=self.state_input.text().strip(),
            country=self.country_input.text().strip() or "Brasil",
            max_per_niche=self.max_per_niche.value(),
            use_ai_qualification=self.use_ai_chk.isChecked(),
            mode=self._strategy_value(),
            selected_products=selected_products,
            preloaded_icp=preloaded_icp,
            preloaded_summary=preloaded_summary,
        )

        self.start_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log_view.clear()
        self.log_view.appendPlainText("Iniciando…")
        if modifiers:
            self.log_view.appendPlainText(
                f"🎯 Sinais ativos: {', '.join(modifiers)}"
            )
        if selected_products:
            self.log_view.appendPlainText(
                "📦 Produtos selecionados: "
                + ", ".join(f"{p['name']} ({p['mode']})" for p in selected_products)
            )

        from app.ui.widgets.run_dialog import ProspectionRunDialog
        dlg = ProspectionRunDialog(self, "Prospecção em andamento", hunt_leads, req)
        dlg.finished.connect(lambda _=0: self._on_dialog_closed(dlg))
        dlg.show()
        dlg.start()
        self._run_dialog = dlg

    def _append_log(self, msg: str, pct: int) -> None:
        self.log_view.appendPlainText(f"[{pct:>3}%] {msg}")
        self.progress.setValue(pct)

    # ---------------------------------------------------------------- analyze
    def _analyze_site(self, force: bool = False) -> None:
        source = self.source_input.text().strip()
        if not source:
            QMessageBox.warning(self, "Atenção",
                                "Cole o site (ou descrição) antes de analisar.")
            return
        is_url = source.startswith(("http://", "https://", "www."))
        is_website = self.is_website_chk.isChecked() and is_url

        self.analyze_btn.setEnabled(False)
        self.reanalyze_btn.setEnabled(False)
        self.analyze_status.setText("⏳ Analisando…" + (" (sem cache)" if force else ""))
        # Limpa produtos anteriores
        self._clear_products()

        from app.ui.widgets.run_dialog import ProspectionRunDialog
        dlg = ProspectionRunDialog(
            self, "Analisando site",
            analyze_business, source, is_website,
            force_refresh=force,
        )
        dlg.finished.connect(lambda _=0: self._on_analysis_dialog_closed(dlg))
        dlg.show()
        dlg.start()
        self._analyze_dialog = dlg

    def _on_analysis_dialog_closed(self, dlg) -> None:
        self.analyze_btn.setEnabled(True)
        self.reanalyze_btn.setEnabled(True)
        if dlg.error:
            self.analyze_status.setText(f"✖ {dlg.error[:80]}")
            QMessageBox.warning(self, "Falha na análise", dlg.error)
            return
        result: AnalysisResult | None = dlg.result
        if result is None:
            self.analyze_status.setText("✖ Sem resposta")
            return
        self._analysis = result
        products = result.icp.products or []
        if not products:
            # Fallback: cria 1 "produto" sintético usando keywords globais
            products = [{
                "name": result.icp.business_type or "Negócio",
                "description": result.icp.summary or "",
                "recommended_mode": result.icp.recommended_mode or "",
                "direct_clients": result.icp.direct_clients,
                "direct_keywords": result.icp.direct_keywords,
                "partner_segments": result.icp.partner_segments,
                "partner_keywords": result.icp.partner_keywords,
            }]
        self._render_products(products)
        self.analyze_status.setText(
            f"✔ {len(products)} produto(s) detectado(s) — "
            f"selecione e clique em Iniciar Prospecção"
        )
        if result.icp.recommended_mode:
            self.highlight_recommendation(result.icp.recommended_mode)

    def _clear_products(self) -> None:
        for c in self._product_cards:
            c.setParent(None)
            c.deleteLater()
        self._product_cards.clear()
        self.products_empty.setVisible(True)
        self.products_section["card"].setVisible(False)

    def _render_products(self, products: list[dict]) -> None:
        self._clear_products()
        self.products_empty.setVisible(False)
        for p in products:
            self._add_product_card(p)
        self.products_section["card"].setVisible(True)

    def _add_product_card(self, p: dict) -> None:
        card = _ProductCard(p)
        card.removed.connect(self._on_product_removed)
        self._product_cards.append(card)
        self.products_container.addWidget(card)
        self.products_section["card"].setVisible(True)
        self.products_empty.setVisible(False)

    def _on_product_removed(self, card: _ProductCard) -> None:
        if card in self._product_cards:
            self._product_cards.remove(card)
        card.setParent(None); card.deleteLater()
        if not self._product_cards:
            self.products_empty.setVisible(True)

    # -------------------------------------------------- adicionar manual
    def _add_product_manually(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Adicionar produto",
            "Nome do produto/serviço que também vende:\n"
            "(ex: 'Pitch Deck', 'Consultoria Tributária')",
        )
        if not ok or not name.strip():
            return
        self.add_product_btn.setEnabled(False)
        self.analyze_status.setText(f"⏳ Gerando keywords para '{name}'…")
        summary = (self._analysis.business_summary if self._analysis else "") \
                  or self.source_input.text().strip()

        from app.ui.widgets.run_dialog import ProspectionRunDialog
        dlg = ProspectionRunDialog(
            self, f"Detalhando produto: {name}",
            generate_product_details, name.strip(), summary,
            with_progress=False,
        )
        dlg.finished.connect(lambda _=0: self._on_manual_product_closed(dlg))
        dlg.show()
        dlg.start()

    def _on_manual_product_closed(self, dlg) -> None:
        self.add_product_btn.setEnabled(True)
        if dlg.error:
            self.analyze_status.setText(f"✖ {dlg.error[:80]}")
            QMessageBox.warning(self, "Falha ao gerar produto", dlg.error)
            return
        product = dlg.result or {}
        if not product.get("name"):
            self.analyze_status.setText("✖ IA não retornou produto válido")
            return
        self._add_product_card(product)
        self.analyze_status.setText(
            f"✔ Produto '{product['name']}' adicionado."
        )

    # -------------------------------------------------- saúde das fontes
    def _check_health(self, include_playwright: bool = False) -> None:
        for dot in self.health_dots.values():
            dot.setText("⏳")
        worker = Worker(check_all, include_playwright=include_playwright)
        run_in_thread(
            self, worker,
            on_finished=self._on_health_done,
            on_failed=lambda _e: None,
        )

    def _on_health_done(self, results) -> None:
        for st in results or []:
            dot = self.health_dots.get(st.name)
            if not dot:
                continue
            dot.setText("🟢" if st.ok else "🔴")
            dot.setToolTip(st.detail or "")

    def _on_dialog_closed(self, dlg) -> None:
        if dlg.error:
            self._on_failed(dlg.error)
        elif dlg.result is not None:
            self._on_finished(dlg.result)
        else:
            self.start_btn.setEnabled(True)

    def _on_finished(self, result) -> None:
        self.start_btn.setEnabled(True)
        self.log_view.appendPlainText(
            f"\n✔ Concluído. {len(result.leads)} leads encontrados "
            f"(diretos={result.direct_count}, parceiros={result.partners_count}, "
            f"search_id={result.search_id})."
        )
        try:
            from app.utils.notifications import notify
            notify("Brainy Prospect — Busca concluída",
                   f"{len(result.leads)} leads encontrados")
        except Exception:  # noqa: BLE001
            pass
        if result.icp.business_type:
            self.log_view.appendPlainText(
                f"\nICP detectado: {result.icp.business_type}"
                f"\nResumo: {result.icp.summary}"
                f"\n\n— Venda Direta —"
                f"\nClientes: {', '.join(result.icp.direct_clients) or '—'}"
                f"\nKeywords: {', '.join(result.icp.direct_keywords) or '—'}"
                f"\n\n— Parceiros —"
                f"\nSegmentos: {', '.join(result.icp.partner_segments) or '—'}"
                f"\nKeywords: {', '.join(result.icp.partner_keywords) or '—'}"
            )
            if result.icp.recommended_mode:
                self.highlight_recommendation(result.icp.recommended_mode)
        self.leads_updated.emit()

    def _on_failed(self, msg: str) -> None:
        self.start_btn.setEnabled(True)
        self.log_view.appendPlainText(f"\n✖ Falhou: {msg}")
        QMessageBox.critical(self, "Erro na prospecção", msg)
