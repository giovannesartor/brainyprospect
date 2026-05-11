"""Janela principal: sidebar moderna hierárquica + páginas."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app import __app_name__, __version__
from app.paths import LOGO_PATH
from app.ui.pages.brainy_chat_page import BrainyChatPage
from app.ui.pages.campaigns_page import CampaignsPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.filtered_pages import (
    DecisoresPage,
    FilteredLeadsPage,
    PlaceholderPage,
)
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.hunt_companies_page import HuntCompaniesPage
from app.ui.pages.icp_page import ICPPage
from app.ui.pages.import_page import ImportPage
from app.ui.pages.leads_page import LeadsPage
from app.ui.pages.logs_page import LogsPage
from app.ui.pages.manual_search_page import ManualSearchPage
from app.ui.pages.mirror_company_page import MirrorCompanyPage
from app.ui.pages.monitoring_page import MonitoringPage
from app.ui.pages.objections_page import ObjectionsPage
from app.ui.pages.pipeline_page import PipelinePage
from app.ui.pages.search_page import SearchPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.today_page import TodayPage
from app.ui.theme import current_theme, toggle_theme


# (parent_label, parent_emoji, [(child_label, key, subtitle)])
NAV_TREE = [
    ("Início", "🏠", [
        ("Dashboard", "dashboard", "Visão geral do seu pipeline"),
        ("🔥 Hoje pra abordar", "crm_today", "Top 10 leads quentes para abordar agora"),
    ]),
    ("Prospectar", "🎯", [
        ("Busca Inteligente", "prospect_smart", "Análise IA + scraping multi-fonte"),
        ("Busca Manual", "prospect_manual", "Você define exatamente o que procurar"),
        ("Empresa Espelho", "prospect_mirror", "Encontre lookalikes do seu cliente ideal"),
        ("Caça Avançada", "prospect_hunt", "Busca por sinais e perfil"),
    ]),
    ("Leads & CRM", "👥", [
        ("Base de Leads", "leads_all", "Base completa com filtros"),
        ("Pipeline (Kanban)", "crm_pipeline", "Leads por etapa do funil"),
        ("Campanhas", "camp_active", "Iniciativas comerciais em andamento"),
        ("Importar CSV/XLSX", "import_leads", "Trazer planilha existente"),
        ("Monitoramento", "mon_companies", "Watch-list comercial"),
    ]),
    ("Inteligência IA", "🧠", [
        ("Brainy Chat", "ai_chat", "Chat estratégico com seus dados"),
        ("Meu ICP", "ai_icp", "Perfil de cliente ideal"),
        ("Quebra de Objeções", "ai_objections", "Argumentos com IA"),
        ("Templates de Mensagem", "cfg_templates", "Editar templates da abordagem"),
    ]),
    ("Sistema", "🛠️", [
        ("Histórico de Buscas", "crm_history", "Pesquisas anteriores"),
        ("Logs & Exportações", "cfg_logs", "Auditoria do sistema"),
        ("Configurações", "cfg_apis", "APIs, scraping, BD, UI"),
    ]),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} — Inteligência Comercial com IA")
        self.resize(1480, 900)
        self.setMinimumSize(1180, 760)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_sidebar(root)
        self._build_content(root)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"{__app_name__} v{__version__} pronto.")

        # cross-page sync
        self.search.leads_updated.connect(self._refresh_data_pages)

        # atalhos de teclado (estilo Gmail / GitHub)
        self._install_shortcuts()

        # estado inicial
        self._switch("dashboard")

    # ------------------------------------------------------------------ build
    def _build_sidebar(self, root: QHBoxLayout) -> None:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(258)

        wrapper = QVBoxLayout(self.sidebar)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)

        # Brand com logo
        brand_box = QWidget()
        bl = QHBoxLayout(brand_box)
        bl.setContentsMargins(16, 16, 16, 8)
        bl.setSpacing(10)
        if LOGO_PATH.exists():
            logo_lbl = QLabel()
            pix = QPixmap(str(LOGO_PATH)).scaledToHeight(
                28, Qt.SmoothTransformation
            )
            logo_lbl.setPixmap(pix)
            bl.addWidget(logo_lbl)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("Brainy Prospect")
        name.setObjectName("brand")
        name.setObjectName("sidebarBrandName")
        ver = QLabel(f"v{__version__} · Inteligência Comercial")
        ver.setObjectName("brand_sub")
        ver.setStyleSheet(
            "color:#6B7280;font-size:10px;text-transform:uppercase;"
            "letter-spacing:1.2px;padding:0"
        )
        brand_text.addWidget(name)
        brand_text.addWidget(ver)
        bl.addLayout(brand_text, 1)
        wrapper.addWidget(brand_box)

        # menu rolável
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_holder = QWidget()
        nav_lay = QVBoxLayout(nav_holder)
        nav_lay.setContentsMargins(0, 4, 0, 8)
        nav_lay.setSpacing(0)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        self._child_to_parent_btn: dict[str, QPushButton] = {}
        self._parent_children: dict[QPushButton, list[QPushButton]] = {}

        for parent_label, emoji, children in NAV_TREE:
            parent_btn = QPushButton(f"  {emoji}   {parent_label}")
            parent_btn.setObjectName("navParent")
            parent_btn.setCursor(Qt.PointingHandCursor)
            parent_btn.setCheckable(False)
            nav_lay.addWidget(parent_btn)

            child_btns: list[QPushButton] = []
            child_container = QWidget()
            cc_lay = QVBoxLayout(child_container)
            cc_lay.setContentsMargins(0, 0, 0, 0)
            cc_lay.setSpacing(0)

            for child_label, key, _sub in children:
                btn = QPushButton(child_label)
                btn.setObjectName("navChild")
                btn.setCheckable(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda _=False, k=key: self._switch(k))
                cc_lay.addWidget(btn)
                self.nav_group.addButton(btn)
                self.nav_buttons[key] = btn
                self._child_to_parent_btn[key] = parent_btn
                child_btns.append(btn)

            nav_lay.addWidget(child_container)
            self._parent_children[parent_btn] = child_btns
            # grupo começa aberto; clique no parent alterna
            parent_btn.clicked.connect(
                lambda _=False, c=child_container: c.setVisible(not c.isVisible())
            )

        nav_lay.addStretch()
        scroll.setWidget(nav_holder)
        wrapper.addWidget(scroll, 1)

        footer = QLabel("⌘ , Configurações")
        footer.setObjectName("footerText")
        wrapper.addWidget(footer)

        root.addWidget(self.sidebar)

    def _build_content(self, root: QHBoxLayout) -> None:
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # header
        self.header = QFrame()
        self.header.setObjectName("header")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(28, 14, 28, 14)
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        self.title_lbl = QLabel("Dashboard"); self.title_lbl.setObjectName("title")
        self.subtitle_lbl = QLabel("Visão geral do seu pipeline")
        self.subtitle_lbl.setObjectName("subtitle")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.subtitle_lbl)
        hl.addLayout(title_box)
        hl.addStretch()

        self.theme_btn = QPushButton("☀️" if current_theme() == "dark" else "🌙")
        self.theme_btn.setObjectName("ghost")
        self.theme_btn.setToolTip("Alternar tema claro/escuro")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setFixedSize(38, 38)
        self.theme_btn.clicked.connect(self._toggle_theme)
        hl.addWidget(self.theme_btn)

        cl.addWidget(self.header)

        # stack
        self.stack = QStackedWidget()
        cl.addWidget(self.stack, 1)
        root.addWidget(content, 1)

        # Páginas REAIS (instanciadas)
        self.dashboard = DashboardPage()
        self.search = SearchPage()
        self.leads = LeadsPage()
        self.leads.leads_changed.connect(self._refresh_data_pages)
        self.pipeline = PipelinePage()
        self.campaigns = CampaignsPage()
        self.history = HistoryPage()
        self.logs = LogsPage()
        self.settings_pg = SettingsPage()
        self.brainy_chat = BrainyChatPage()
        self.decisores = DecisoresPage()
        self.import_pg = ImportPage()
        self.import_pg.leads_updated.connect(self._refresh_data_pages)
        self.objections = ObjectionsPage()
        self.monitoring = MonitoringPage()
        self.icp_pg = ICPPage()
        self.today = TodayPage()
        self.today.leads_changed.connect(self._refresh_data_pages)
        self.leads_hot = FilteredLeadsPage(priority="maxima")
        self.leads_partners_premium = FilteredLeadsPage(mode="partners", min_score=80)
        self.leads_favorites = FilteredLeadsPage(tag="Favorito")

        # Mapeamento de chaves -> (widget, title, subtitle)
        self._pages: dict[str, tuple[QWidget, str, str]] = {}

        def reg(key: str, widget: QWidget, title: str, sub: str):
            self._pages[key] = (widget, title, sub)
            self.stack.addWidget(widget)

        reg("dashboard", self.dashboard, "Dashboard", "Visão executiva do seu negócio")

        # Prospectar
        reg("prospect_smart", self.search, "Busca Inteligente",
            "Análise IA + scraping multi-fonte")
        self.manual_search = ManualSearchPage()
        self.manual_search.leads_updated.connect(self._refresh_data_pages)
        reg("prospect_manual", self.manual_search,
            "Busca Manual", "Você define exatamente o que procurar")
        self.mirror = MirrorCompanyPage()
        self.mirror.leads_updated.connect(self._refresh_data_pages)
        reg("prospect_mirror", self.mirror,
            "Empresa Espelho", "Encontre lookalikes do seu melhor cliente")
        self.hunt = HuntCompaniesPage()
        self.hunt.leads_updated.connect(self._refresh_data_pages)
        reg("prospect_hunt", self.hunt,
            "Caça Empresas", "Modo avançado por sinais comerciais")
        reg("prospect_tech", PlaceholderPage(
            "Busca por Tecnologia",
            "Encontre empresas pela stack: HubSpot, RD Station, Shopify, SAP, VTEX, "
            "WordPress, Stripe e mais. A detecção já existe — em breve buscas dedicadas.",
            ["24+ assinaturas detectáveis", "Filtros combinados",
             "Score por fit tecnológico"], "🧩"),
            "Busca por Tecnologia", "Empresas por stack instalada")

        # Leads
        reg("leads_all", self.leads, "Todos os Leads", "Base completa de leads")
        reg("import_leads", self.import_pg, "Importar Leads",
            "CSV/XLSX com mapeamento de colunas")
        reg("leads_hot", self.leads_hot, "Oportunidades Quentes",
            "🔥 Leads de prioridade máxima")
        reg("leads_partners_premium", self.leads_partners_premium,
            "Parceiros Premium", "🤝 Multiplicadores estratégicos com score ≥ 80")
        reg("leads_favorites", self.leads_favorites, "Favoritos",
            "Leads marcados como prioritários (tag Favorito)")
        reg("leads_decisors", self.decisores, "Decisores",
            "CEOs, fundadores, sócios e diretores extraídos")

        # Campanhas
        reg("camp_active", self.campaigns, "Campanhas Ativas",
            "Iniciativas comerciais em andamento")
        reg("camp_closed", PlaceholderPage(
            "Campanhas Encerradas",
            "Histórico completo das campanhas finalizadas com métricas.",
            ["ROI por campanha", "Análise de fechamento",
             "Lições aprendidas"], "📦"),
            "Campanhas Encerradas", "Histórico de campanhas")
        reg("camp_templates", PlaceholderPage(
            "Templates Comerciais",
            "Modelos prontos de abordagem por canal e por nicho.",
            ["WhatsApp / Email / LinkedIn",
             "Variáveis dinâmicas", "Versões A/B"], "📨"),
            "Templates Comerciais", "Modelos prontos de abordagem")
        reg("camp_playbooks", PlaceholderPage(
            "Playbooks por Nicho",
            "Estratégias completas: Contabilidade, Advogados, Startups, Holdings, M&A.",
            ["Argumentos prontos", "Quebra de objeções",
             "CTAs adaptados"], "📘"),
            "Playbooks", "Estratégias por nicho")

        # CRM
        reg("crm_pipeline", self.pipeline, "Pipeline CRM",
            "Kanban dos leads por etapa do funil")
        reg("crm_today", self.today, "Hoje você deve abordar",
            "Top 10 leads quentes + follow-ups vencidos")
        # alias: o item de menu "Follow-ups" também aponta pra Today
        self._pages["crm_followups"] = self._pages["crm_today"]
        reg("crm_history", self.history, "Histórico", "Pesquisas anteriores")
        reg("crm_tasks", PlaceholderPage(
            "Tarefas Comerciais",
            "Lista de tarefas com prioridade, prazo e responsável.",
            ["Vinculadas ao lead", "Lembretes",
             "Integração com calendário"], "✅"),
            "Tarefas", "Lista de tarefas comerciais")

        # IA
        reg("ai_chat", self.brainy_chat, "Brainy AI Assistant",
            "Chat estratégico com seus dados")
        reg("ai_icp", self.icp_pg, "Meu ICP",
            "Perfil de cliente ideal + recomputar prioridades")
        reg("ai_analysis", PlaceholderPage(
            "Análise de Empresa",
            "Gere um dossiê comercial completo de qualquer empresa em segundos.",
            ["Resumo do negócio", "Sinais detectados",
             "Decisores", "Match comercial"], "🔍"),
            "Análise de Empresa", "Dossiê empresarial completo")
        reg("ai_match", PlaceholderPage(
            "Match Comercial",
            "Compare seu negócio com qualquer lead e veja % de compatibilidade.",
            ["Score de match já gerado nos leads",
             "Em breve: comparação 1-a-1",
             "Sugestões de oferta"], "🎯"),
            "Match Comercial", "Compatibilidade negócio × lead")
        reg("ai_forecast", PlaceholderPage(
            "Previsão de Fechamento",
            "IA estima probabilidade de conversão de cada lead/proposta.",
            ["Modelagem por histórico",
             "Confiança por etapa", "Forecast mensal"], "🔮"),
            "Previsão de Fechamento", "Probabilidade de conversão")
        reg("ai_objections", self.objections,
            "IA de Objeções", "Quebra de objeções com IA")
        reg("ai_copy", PlaceholderPage(
            "IA de Copy",
            "Gere mensagens prontas para WhatsApp, email, LinkedIn e scripts de cold call.",
            ["Pitch já gerado por lead",
             "Em breve: gerador independente",
             "Templates personalizáveis"], "✏️"),
            "IA de Copy", "WhatsApp, email, LinkedIn, scripts")

        # Monitoramento
        reg("mon_companies", self.monitoring,
            "Empresas Monitoradas", "Watch-list comercial")
        reg("mon_changes", self.monitoring,
            "Alterações Detectadas", "Mudanças nas empresas observadas")
        reg("mon_alerts", PlaceholderPage(
            "Alertas Inteligentes",
            "Receba alertas quando um sinal estratégico for detectado.",
            ["Disparo via app/email",
             "Configuração por tipo de sinal",
             "Priorização automática"], "🔔"),
            "Alertas Inteligentes", "Triggers automáticos")

        # Parceiros
        reg("partners_active", PlaceholderPage(
            "Parceiros Ativos",
            "Visão exclusiva dos parceiros em relacionamento comercial.",
            ["Indicações recebidas", "Conversões",
             "Receita gerada"], "🤝"),
            "Parceiros Ativos", "Canais em relacionamento")
        reg("partners_premium", FilteredLeadsPage(mode="partners", min_score=85),
            "Parceiros Premium", "🤝 Multiplicadores com score ≥ 85")
        reg("partners_revenue", PlaceholderPage(
            "Receita Estimada por Parceiro",
            "Projeção financeira baseada na carteira potencial dos parceiros.",
            ["Estimativa mensal/anual", "Top 10 parceiros",
             "Curva de receita"], "💰"),
            "Receita Estimada", "Potencial financeiro dos parceiros")
        reg("partners_potential", PlaceholderPage(
            "Potencial de Indicação",
            "Ranking de parceiros por capacidade de gerar indicações.",
            ["Score de carteira",
             "Frequência estimada de indicações",
             "Nicho de impacto"], "📈"),
            "Potencial de Indicação", "Capacidade indicativa")

        # Analytics
        for k, t, sub, emoji in [
            ("an_conversion", "Conversão", "Funil e taxas de conversão", "🔁"),
            ("an_performance", "Performance Comercial",
             "Velocidade e produtividade do funil", "🚀"),
            ("an_regions", "Regiões Mais Fortes",
             "Geografia da prospecção", "🗺️"),
            ("an_niches", "Nichos Mais Lucrativos",
             "Onde está a receita", "💎"),
            ("an_heatmap", "Heatmap Comercial",
             "Mapa de calor por região", "🌎"),
        ]:
            reg(k, PlaceholderPage(
                t, "Painel analítico em construção. "
                "Os dados já estão sendo coletados e estarão disponíveis em breve.",
                ["Gráficos modernos", "Filtros cruzados",
                 "Exportação"], emoji),
                t, sub)

        # Automação
        reg("auto_rules", PlaceholderPage(
            "Regras de Automação",
            "Crie regras como: SE score > 90 ENTÃO mover para campanha 'Premium'.",
            ["Editor visual", "Triggers múltiplos",
             "Histórico de execução"], "⚙️"),
            "Regras", "SE/ENTÃO comercial")
        reg("auto_followups", PlaceholderPage(
            "Follow-ups Automáticos",
            "Disparos automáticos por inatividade do lead.",
            ["Cadência configurável", "Mensagens via IA",
             "Pausa em resposta"], "📤"),
            "Follow-ups Automáticos", "Disparos por inatividade")
        reg("auto_ai", PlaceholderPage(
            "IA Automática",
            "Pipelines orquestrados por IA: do scraping ao follow-up.",
            ["Workflows nativos", "Integrações futuras",
             "Logs de execução"], "🧪"),
            "IA Automática", "Pipelines orquestrados por IA")

        # Documentos
        for k, t, sub, emoji in [
            ("doc_proposals", "Propostas",
             "Geração de propostas comerciais", "📑"),
            ("doc_contracts", "Contratos",
             "Modelos e versionamento", "📜"),
            ("doc_pitchdecks", "Pitch Decks",
             "Apresentações comerciais", "🎤"),
            ("doc_pdfs", "PDFs",
             "Biblioteca de arquivos", "📁"),
        ]:
            reg(k, PlaceholderPage(
                t, "Módulo de documentos comerciais em construção.",
                ["Templates personalizáveis", "Mesclagem de dados",
                 "Exportação em PDF"], emoji), t, sub)

        # Configurações — usa página unificada existente para várias chaves
        reg("cfg_apis", self.settings_pg, "APIs", "DeepSeek / OpenAI")
        reg("cfg_scraping", self.settings_pg, "Scraping",
            "Delay, proxy, timeout")
        reg("cfg_db", PlaceholderPage(
            "Banco de Dados",
            "SQLite local ativo. Suporte a PostgreSQL em breve.",
            ["Migração para Postgres",
             "Backup automático", "Importação de bases externas"], "🗄️"),
            "Banco de Dados", "Configuração de persistência")
        reg("cfg_exports", PlaceholderPage(
            "Exportações",
            "Configurações de exportação. Exportar leads continua disponível "
            "diretamente na tela de Leads.",
            ["Colunas padrão", "Pasta destino",
             "Agendamento futuro"], "📤"),
            "Exportações", "CSV, XLSX, JSON")
        reg("cfg_ui", PlaceholderPage(
            "Interface",
            "Tema dark elegante ativo. Mais opções de personalização em breve.",
            ["Temas alternativos", "Idiomas (PT/EN/ES)",
             "Densidade de layout"], "🎨"),
            "Interface", "Aparência e UX")
        reg("cfg_logs", self.logs, "Logs & Exportações",
            "Auditoria do sistema")
        reg("cfg_templates", self.settings_pg, "Templates de Mensagem",
            "Edite o template de venda direta e parceiros")

    # ------------------------------------------------------------------ nav
    def _switch(self, key: str) -> None:
        if key not in self._pages:
            return
        page, title, subtitle = self._pages[key]
        self.stack.setCurrentWidget(page)
        self.title_lbl.setText(title)
        self.subtitle_lbl.setText(subtitle)
        # marca botão sem disparar evento
        btn = self.nav_buttons.get(key)
        if btn and not btn.isChecked():
            btn.setChecked(True)
        # auto-refresh
        for attr_key, attr_name in [
            ("dashboard", "dashboard"), ("leads_all", "leads"),
            ("crm_pipeline", "pipeline"), ("camp_active", "campaigns"),
            ("crm_history", "history"), ("cfg_logs", "logs"),
            ("leads_hot", "leads_hot"),
            ("leads_partners_premium", "leads_partners_premium"),
            ("leads_favorites", "leads_favorites"),
            ("leads_decisors", "decisores"),
            ("partners_premium", None),
        ]:
            if key == attr_key and attr_name and hasattr(self, attr_name):
                obj = getattr(self, attr_name)
                if hasattr(obj, "reload"):
                    obj.reload()

    def _refresh_data_pages(self) -> None:
        for obj in (self.dashboard, self.leads, self.pipeline, self.history,
                    self.leads_hot, self.leads_partners_premium,
                    self.leads_favorites, self.decisores, self.today):
            if hasattr(obj, "reload"):
                obj.reload()

    def _toggle_theme(self) -> None:
        new_theme = toggle_theme()
        self.theme_btn.setText("☀️" if new_theme == "dark" else "🌙")
        self.statusBar().showMessage(
            f"Tema {'escuro' if new_theme == 'dark' else 'claro'} aplicado.", 3000
        )

    # API pública para outras páginas navegarem
    def navigate_to(self, key: str) -> None:
        self._switch(key)

    def _install_shortcuts(self) -> None:
        """Atalhos: ⌘K abre busca; G,X navega rápido."""
        # navegação rápida estilo Gmail
        mapping = [
            ("G,D", "dashboard"),
            ("G,S", "prospect_smart"),
            ("G,M", "prospect_manual"),
            ("G,L", "leads_all"),
            ("G,P", "crm_pipeline"),
            ("G,C", "camp_active"),
            ("G,O", "ai_objections"),
            ("G,I", "ai_icp"),
            ("G,W", "mon_companies"),
            ("G,H", "ai_chat"),
        ]
        for seq, key in mapping:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(lambda k=key: self._switch(k))
        # toggle de tema
        QShortcut(QKeySequence("Ctrl+Shift+T"), self,
                  activated=self._toggle_theme)
        # focar busca
        QShortcut(QKeySequence("Ctrl+L"), self,
                  activated=lambda: self._switch("leads_all"))

    # --------------------------- shutdown seguro ---------------------------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Aguarda QThreads filhas terminarem antes de fechar para evitar
        crash 'QThread: Destroyed while thread is still running' no shutdown.
        """
        try:
            threads = self.findChildren(QThread)
            for th in threads:
                try:
                    if th.isRunning():
                        th.requestInterruption()
                        th.quit()
                        # espera curta — não trava UI por muito tempo
                        th.wait(2000)
                except Exception:
                    pass
        except Exception:
            pass
        super().closeEvent(event)
