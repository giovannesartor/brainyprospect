"""Tela de Configurações."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import get_settings, update_settings
from app.ui.widgets.cards import SectionTitle


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        root.addWidget(SectionTitle("Configurações"))

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_ai_tab(), "🧠  IA")
        self.tabs.addTab(self._build_scraping_tab(), "🌐  Scraping")
        self.tabs.addTab(self._build_messages_tab(), "💬  Mensagens")

        actions = QHBoxLayout()
        actions.addStretch()
        self.save_btn = QPushButton("Salvar configurações")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(self.save_btn)
        root.addLayout(actions)

        self._load()

    def _build_ai_tab(self) -> QWidget:
        ai_card = QFrame(); ai_card.setObjectName("card")
        ai_lay = QFormLayout(ai_card); ai_lay.setContentsMargins(20, 16, 20, 16)
        self.provider = QComboBox(); self.provider.addItems(["deepseek", "openai"])
        self.deepseek_key = QLineEdit(); self.deepseek_key.setEchoMode(QLineEdit.Password)
        self.deepseek_model = QLineEdit()
        self.openai_key = QLineEdit(); self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_model = QLineEdit()
        ai_lay.addRow("Provider padrão", self.provider)
        ai_lay.addRow("DeepSeek API Key", self.deepseek_key)
        ai_lay.addRow("DeepSeek Model", self.deepseek_model)
        ai_lay.addRow("OpenAI API Key", self.openai_key)
        ai_lay.addRow("OpenAI Model", self.openai_model)
        return ai_card

    def _build_scraping_tab(self) -> QWidget:
        sc_card = QFrame(); sc_card.setObjectName("card")
        sc_lay = QFormLayout(sc_card); sc_lay.setContentsMargins(20, 16, 20, 16)
        self.timeout = QSpinBox(); self.timeout.setRange(5, 120); self.timeout.setSuffix(" s")
        self.delay_min = QSpinBox(); self.delay_min.setRange(0, 10000); self.delay_min.setSuffix(" ms")
        self.delay_max = QSpinBox(); self.delay_max.setRange(0, 20000); self.delay_max.setSuffix(" ms")
        self.retries = QSpinBox(); self.retries.setRange(0, 10)
        self.max_results = QSpinBox(); self.max_results.setRange(5, 200)
        self.proxy = QLineEdit(); self.proxy.setPlaceholderText("http://user:pass@host:port (opcional)")
        sc_lay.addRow("Timeout HTTP", self.timeout)
        sc_lay.addRow("Delay mínimo", self.delay_min)
        sc_lay.addRow("Delay máximo", self.delay_max)
        sc_lay.addRow("Tentativas", self.retries)
        sc_lay.addRow("Resultados/busca", self.max_results)
        sc_lay.addRow("Proxy", self.proxy)
        return sc_card

    def _build_messages_tab(self) -> QWidget:
        wrap = QWidget()
        outer = QVBoxLayout(wrap); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(10)

        info = QLabel(
            "<b>Templates de mensagem.</b> Use placeholders: "
            "<code>{nome}</code>, <code>{cidade}</code>, <code>{uf}</code>, "
            "<code>{nicho}</code>, <code>{site}</code>, <code>{decisor_first}</code>, "
            "<code>{abertura}</code> (frase gerada pela IA por lead)."
        )
        info.setWordWrap(True)
        info.setObjectName("muted"); info.setStyleSheet("padding:4px 0")
        outer.addWidget(info)

        sender_card = QFrame(); sender_card.setObjectName("card")
        sl = QFormLayout(sender_card); sl.setContentsMargins(20, 12, 20, 12)
        self.sender_name = QLineEdit(); self.sender_name.setPlaceholderText("Seu nome (ex.: João da Silva)")
        self.sender_company = QLineEdit()
        self.sender_site = QLineEdit()
        sl.addRow("Seu nome", self.sender_name)
        sl.addRow("Sua empresa", self.sender_company)
        sl.addRow("Seu site", self.sender_site)
        outer.addWidget(sender_card)

        opt_card = QFrame(); opt_card.setObjectName("card")
        ol = QVBoxLayout(opt_card); ol.setContentsMargins(20, 12, 20, 12); ol.setSpacing(6)
        self.use_ai_opener = QCheckBox("Gerar abertura personalizada com IA por lead ({abertura})")
        self.generate_ab = QCheckBox("Gerar variantes A/B (2 versões)")
        self.use_ai_full = QCheckBox("Modo IA Full — escrever o CORPO INTEIRO da mensagem por lead (mais lento, mais personalizado)")
        ol.addWidget(self.use_ai_opener)
        ol.addWidget(self.generate_ab)
        ol.addWidget(self.use_ai_full)
        outer.addWidget(opt_card)

        # ações: refazer onboarding/tour, regenerar templates
        actions_card = QFrame(); actions_card.setObjectName("card")
        al = QHBoxLayout(actions_card); al.setContentsMargins(20, 10, 20, 10)
        self.btn_redo_onboarding = QPushButton("↻ Refazer onboarding")
        self.btn_redo_tour = QPushButton("🎯 Refazer tour")
        self.btn_regen_templates = QPushButton("✨ Regerar templates com IA")
        self.btn_redo_onboarding.clicked.connect(self._redo_onboarding)
        self.btn_redo_tour.clicked.connect(self._redo_tour)
        self.btn_regen_templates.clicked.connect(self._regen_templates)
        al.addWidget(self.btn_redo_onboarding)
        al.addWidget(self.btn_redo_tour)
        al.addWidget(self.btn_regen_templates)
        al.addStretch(1)
        outer.addWidget(actions_card)

        tpl_tabs = QTabWidget()
        outer.addWidget(tpl_tabs, 1)

        self.partner_tpl = self._mk_editor()
        tpl_tabs.addTab(self._wrap(self.partner_tpl), "Parceiros")

        self.direct_tpl = self._mk_editor()
        tpl_tabs.addTab(self._wrap(self.direct_tpl), "Venda Direta")

        fu_wrap = QWidget(); fu_lay = QVBoxLayout(fu_wrap); fu_lay.setContentsMargins(0, 0, 0, 0)
        self.fu1 = self._mk_editor(min_h=110)
        self.fu2 = self._mk_editor(min_h=110)
        self.fu3 = self._mk_editor(min_h=110)
        for label, ed in [("Follow-up 1 (D+3)", self.fu1),
                          ("Follow-up 2 (D+7)", self.fu2),
                          ("Follow-up 3 (D+15)", self.fu3)]:
            l = QLabel(label); l.setObjectName("fieldLabel"); l.setStyleSheet("margin-top:6px")
            fu_lay.addWidget(l); fu_lay.addWidget(ed)
        tpl_tabs.addTab(fu_wrap, "Follow-ups")
        return wrap

    def _mk_editor(self, min_h: int = 220) -> QPlainTextEdit:
        ed = QPlainTextEdit(); ed.setMinimumHeight(min_h)
        ed.setStyleSheet(
            "QPlainTextEdit{background:#0B0F19;color:#E6E8EE;border:1px solid #1F2937;"
            "border-radius:8px;padding:10px;font-family:'SF Mono',Menlo,monospace;font-size:12px}"
        )
        return ed

    def _wrap(self, ed: QPlainTextEdit) -> QWidget:
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0, 0, 0, 0); l.addWidget(ed)
        return w

    def _load(self) -> None:
        s = get_settings(reload=True)
        self.provider.setCurrentText(s.ai.default_provider)
        self.deepseek_key.setText(s.ai.deepseek.api_key)
        self.deepseek_model.setText(s.ai.deepseek.model)
        self.openai_key.setText(s.ai.openai.api_key)
        self.openai_model.setText(s.ai.openai.model)

        self.timeout.setValue(s.scraping.timeout_seconds)
        self.delay_min.setValue(s.scraping.min_delay_ms)
        self.delay_max.setValue(s.scraping.max_delay_ms)
        self.retries.setValue(s.scraping.max_retries)
        self.max_results.setValue(s.scraping.max_results_per_search)
        self.proxy.setText(s.scraping.proxy)

        self.sender_name.setText(s.messages.sender_name)
        self.sender_company.setText(s.messages.sender_company)
        self.sender_site.setText(s.messages.sender_site)
        self.use_ai_opener.setChecked(s.messages.use_ai_opener)
        self.generate_ab.setChecked(s.messages.generate_ab_variants)
        self.use_ai_full.setChecked(getattr(s.messages, "use_ai_full_message", False))
        self.partner_tpl.setPlainText(s.messages.partner_template)
        self.direct_tpl.setPlainText(s.messages.direct_template)
        self.fu1.setPlainText(s.messages.followup_1)
        self.fu2.setPlainText(s.messages.followup_2)
        self.fu3.setPlainText(s.messages.followup_3)

    def _save(self) -> None:
        s = get_settings()
        s.ai.default_provider = self.provider.currentText()
        s.ai.deepseek.api_key = self.deepseek_key.text().strip()
        s.ai.deepseek.model = self.deepseek_model.text().strip() or "deepseek-chat"
        s.ai.openai.api_key = self.openai_key.text().strip()
        s.ai.openai.model = self.openai_model.text().strip() or "gpt-4o-mini"

        s.scraping.timeout_seconds = self.timeout.value()
        s.scraping.min_delay_ms = self.delay_min.value()
        s.scraping.max_delay_ms = max(self.delay_max.value(), self.delay_min.value())
        s.scraping.max_retries = self.retries.value()
        s.scraping.max_results_per_search = self.max_results.value()
        s.scraping.proxy = self.proxy.text().strip()

        s.messages.sender_name = self.sender_name.text().strip()
        s.messages.sender_company = self.sender_company.text().strip()
        s.messages.sender_site = self.sender_site.text().strip()
        s.messages.use_ai_opener = self.use_ai_opener.isChecked()
        s.messages.generate_ab_variants = self.generate_ab.isChecked()
        s.messages.use_ai_full_message = self.use_ai_full.isChecked()
        s.messages.partner_template = self.partner_tpl.toPlainText()
        s.messages.direct_template = self.direct_tpl.toPlainText()
        s.messages.followup_1 = self.fu1.toPlainText()
        s.messages.followup_2 = self.fu2.toPlainText()
        s.messages.followup_3 = self.fu3.toPlainText()

        update_settings(s)
        QMessageBox.information(self, "Configurações", "Salvo com sucesso.")

    # ---------- ações de onboarding/tour ----------
    def _redo_onboarding(self) -> None:
        from PySide6.QtCore import QSettings
        QSettings("BrainyProspect", "BrainyProspect").setValue("app/onboarded", False)
        from app.ui.onboarding import OnboardingWizard
        wiz = OnboardingWizard(self.window())
        wiz.exec()
        self._load()
        QMessageBox.information(self, "Onboarding", "Configuração refeita. Templates atualizados.")

    def _redo_tour(self) -> None:
        from app.ui.tour import maybe_run as tour_run
        tour_run(self.window(), force=True)

    def _regen_templates(self) -> None:
        from app.services import user_icp
        icp = user_icp.load()
        if not icp:
            QMessageBox.warning(self, "Sem ICP", "Faça o onboarding antes de gerar os templates.")
            return
        from app.services.messaging import generate_templates_from_icp
        QMessageBox.information(self, "Gerando…", "A IA vai escrever seus templates. Pode levar alguns segundos.")
        tpls = generate_templates_from_icp(icp)
        if not tpls:
            QMessageBox.warning(self, "Falha", "Não consegui gerar templates (verifique chave de IA).")
            return
        s = get_settings()
        if tpls.get("direct"):     s.messages.direct_template = tpls["direct"]
        if tpls.get("partner"):    s.messages.partner_template = tpls["partner"]
        if tpls.get("followup_1"): s.messages.followup_1 = tpls["followup_1"]
        if tpls.get("followup_2"): s.messages.followup_2 = tpls["followup_2"]
        if tpls.get("followup_3"): s.messages.followup_3 = tpls["followup_3"]
        update_settings(s)
        self._load()
        QMessageBox.information(self, "Templates", "Templates regenerados com sucesso.")
