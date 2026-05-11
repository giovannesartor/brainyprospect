"""Wizard de onboarding inicial — coleta ICP completo + gera templates via IA."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from app.services import user_icp


class _WelcomePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Bem-vindo ao Brainy Prospect")
        self.setSubTitle("Em 2 minutos a IA já trabalha do seu lado. Vamos configurar.")
        lay = QVBoxLayout(self)
        msg = QLabel(
            "O Brainy é seu agente de prospecção:\n\n"
            "• Encontra empresas pelo Google + IA\n"
            "• Analisa sites em busca de oportunidades\n"
            "• Prioriza leads com base no SEU negócio\n"
            "• Escreve mensagens WhatsApp personalizadas para cada lead\n\n"
            "Vou te fazer algumas perguntas pra montar tudo automaticamente."
        )
        msg.setWordWrap(True)
        lay.addWidget(msg)


class _ICPPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Seu negócio")
        self.setSubTitle("Conta o que você vende e pra quem.")
        lay = QVBoxLayout(self)

        self.company = QLineEdit(); self.company.setPlaceholderText("Ex: Quanto Vale, ACME Consultoria…")
        self.site = QLineEdit(); self.site.setPlaceholderText("https://seusite.com.br")
        self.what = QPlainTextEdit()
        self.what.setPlaceholderText(
            "Em 2-3 linhas: o que você vende e qual o problema que resolve?\n"
            "Ex: 'Faço valuation de empresas com metodologia DCF — útil quando vão vender, captar investidor ou entrada de sócio.'"
        )
        self.what.setMinimumHeight(80)
        self.who = QPlainTextEdit()
        self.who.setPlaceholderText(
            "Cliente ideal: quem é, qual a dor, qual o momento?\n"
            "Ex: 'Empresas de R$ 1M a R$ 50M faturamento, pensando em sair ou trazer sócio.'"
        )
        self.who.setMinimumHeight(80)

        lay.addWidget(QLabel("Nome da sua empresa")); lay.addWidget(self.company)
        lay.addWidget(QLabel("Seu site")); lay.addWidget(self.site)
        lay.addWidget(QLabel("O que você vende (pitch curto)")); lay.addWidget(self.what)
        lay.addWidget(QLabel("Cliente ideal (ICP)")); lay.addWidget(self.who)

        self.registerField("company*", self.company)
        self.registerField("site", self.site)
        self.registerField("what*", self.what, "plainText")
        self.registerField("who", self.who, "plainText")


class _OfferPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Sua oferta")
        self.setSubTitle("Diferenciais, ticket e como você quer fechar.")
        lay = QVBoxLayout(self)

        self.diff = QPlainTextEdit()
        self.diff.setPlaceholderText(
            "O que te diferencia da concorrência? (1-3 linhas)\n"
            "Ex: 'Laudo em 24h vs. 30 dias da consultoria; preço 10x menor; metodologia institucional.'"
        )
        self.diff.setMinimumHeight(70)
        self.ticket = QLineEdit(); self.ticket.setPlaceholderText("Ex: R$ 1.297 a R$ 4.997")
        self.cta = QLineEdit(); self.cta.setPlaceholderText("Ex: 'agendar 15 min', 'enviar exemplo do laudo', 'fazer demo'")
        self.tone = QComboBox()
        self.tone.addItems(["Equilibrado (recomendado)", "Mais formal", "Mais casual"])

        lay.addWidget(QLabel("Diferenciais")); lay.addWidget(self.diff)
        lay.addWidget(QLabel("Ticket médio (faixa)")); lay.addWidget(self.ticket)
        lay.addWidget(QLabel("Chamada para ação preferida (CTA)")); lay.addWidget(self.cta)
        lay.addWidget(QLabel("Tom de voz das mensagens")); lay.addWidget(self.tone)

        self.registerField("diff", self.diff, "plainText")
        self.registerField("ticket", self.ticket)
        self.registerField("cta", self.cta)
        self.registerField("tone_idx", self.tone, "currentIndex")


class _PartnerPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Programa de parceiros (opcional)")
        self.setSubTitle("Se você tem programa de indicação/parceria, vamos usar nas mensagens.")
        lay = QVBoxLayout(self)

        self.has_partner = QCheckBox("Sim, eu tenho programa de parceiros / indicação")
        self.terms = QPlainTextEdit()
        self.terms.setPlaceholderText(
            "Termos: % de comissão, faixas, forma de pagamento, recorrência…\n"
            "Ex: '50% por indicação fechada, via PIX, sem mensalidade. R$ 648 por venda do plano básico.'"
        )
        self.terms.setMinimumHeight(110)
        self.terms.setEnabled(False)
        self.has_partner.toggled.connect(self.terms.setEnabled)

        lay.addWidget(self.has_partner)
        lay.addWidget(QLabel("Detalhes do programa"))
        lay.addWidget(self.terms)

        self.registerField("has_partner", self.has_partner)
        self.registerField("partner_terms", self.terms, "plainText")


class _GeneratePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Configurando seu Brainy")
        self.setSubTitle("Vou usar a IA pra escrever seus templates de mensagem com base no que você me contou.")
        lay = QVBoxLayout(self)
        self.status = QLabel(
            "Pronto! Clique em <b>Concluir</b> pra eu gerar seus templates "
            "personalizados e abrir o tour rápido pelo app."
        )
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.hide()
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        lay.addStretch(1)


class OnboardingWizard(QWizard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Brainy Prospect — Onboarding")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(680, 560)

        self._welcome = _WelcomePage()
        self._icp = _ICPPage()
        self._offer = _OfferPage()
        self._partner = _PartnerPage()
        self._gen = _GeneratePage()

        self.addPage(self._welcome)
        self.addPage(self._icp)
        self.addPage(self._offer)
        self.addPage(self._partner)
        self.addPage(self._gen)

        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.button(QWizard.FinishButton).clicked.connect(self._save_and_generate)

    def _collect_icp(self) -> dict:
        tones = {0: "equilibrado", 1: "formal", 2: "casual"}
        return {
            "company_name": self._icp.company.text().strip(),
            "website": self._icp.site.text().strip(),
            "business_summary": self._icp.what.toPlainText().strip(),
            "ideal_client": self._icp.who.toPlainText().strip(),
            "differentials": self._offer.diff.toPlainText().strip(),
            "avg_ticket": self._offer.ticket.text().strip(),
            "cta": self._offer.cta.text().strip(),
            "tone": tones.get(self._offer.tone.currentIndex(), "equilibrado"),
            "partner_program": self._partner.has_partner.isChecked(),
            "partner_terms": (
                self._partner.terms.toPlainText().strip()
                if self._partner.has_partner.isChecked()
                else ""
            ),
        }

    def _save_and_generate(self) -> None:
        icp = self._collect_icp()
        user_icp.save(icp)

        try:
            from app.config import get_settings, update_settings
            s = get_settings(reload=True)
            s.messages.sender_company = icp["company_name"]
            s.messages.sender_site = icp["website"]
            update_settings(s)
        except Exception:
            pass

        try:
            from app.services.messaging import generate_templates_from_icp
            from app.config import get_settings, update_settings
            tpls = generate_templates_from_icp(icp)
            if tpls:
                s = get_settings(reload=True)
                if tpls.get("direct"):
                    s.messages.direct_template = tpls["direct"]
                if tpls.get("partner"):
                    s.messages.partner_template = tpls["partner"]
                if tpls.get("followup_1"):
                    s.messages.followup_1 = tpls["followup_1"]
                if tpls.get("followup_2"):
                    s.messages.followup_2 = tpls["followup_2"]
                if tpls.get("followup_3"):
                    s.messages.followup_3 = tpls["followup_3"]
                update_settings(s)
        except Exception as e:  # noqa: BLE001
            from app.utils.logger import get_logger
            get_logger("onboarding").warning(f"Falha ao gerar templates IA: {e}")

        QSettings("BrainyProspect", "BrainyProspect").setValue("app/onboarded", True)


def maybe_run(parent: QWidget | None = None) -> None:
    s = QSettings("BrainyProspect", "BrainyProspect")
    onboarded = s.value("app/onboarded", False, bool)

    if not onboarded and not user_icp.is_configured():
        wiz = OnboardingWizard(parent)
        wiz.exec()
        # após onboarding, sempre abre o tour
        try:
            from app.ui.tour import maybe_run as tour_maybe_run
            tour_maybe_run(parent, force=True)
        except Exception:
            pass
        return

    if not onboarded:
        s.setValue("app/onboarded", True)

    # já onboarded — roda tour 1x se ainda não viu
    try:
        from app.ui.tour import maybe_run as tour_maybe_run
        tour_maybe_run(parent)
    except Exception:
        pass
