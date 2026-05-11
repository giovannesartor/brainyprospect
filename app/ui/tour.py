"""Tour interativo guiado pelas principais áreas do app.

Mostra um overlay modal com bullets explicando cada seção. Roda 1x após
o onboarding (controlado por QSettings 'app/tour_done').
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import colors as theme_colors


_STEPS: list[tuple[str, str]] = [
    (
        "Bem-vindo ao tour rápido 🎯",
        "Vou te mostrar em 1 minuto onde fica cada coisa importante. "
        "Você pode pular a qualquer momento.",
    ),
    (
        "Hoje — sua fila do dia",
        "A página <b>Hoje</b> mostra os leads quentes para abordar agora "
        "e os follow-ups do dia. Clicar em <b>WhatsApp</b> ou <b>Email</b> "
        "abre a conversa <i>e marca como enviado</i>, sumindo da lista.",
    ),
    (
        "Prospecção — encontrar empresas",
        "Em <b>Busca Inteligente</b>, <b>Buscar Manualmente</b>, "
        "<b>Caçar Empresas</b> e <b>Espelhar Cliente</b> você dispara "
        "a IA pra coletar leads do Google, Bing, DuckDuckGo e Maps.",
    ),
    (
        "Leads — sua base",
        "<b>Todos os Leads</b>, <b>Quentes</b>, <b>Parceiros</b> e "
        "<b>Decisores</b> filtram a base. Clique num lead pra ver detalhe, "
        "histórico, mensagem pronta e botões de ação.",
    ),
    (
        "Pipeline & Histórico",
        "<b>Pipeline</b> = Kanban (Novo → Qualificado → Contatado → "
        "Em conversa → Reunião → Cliente). "
        "<b>Histórico</b> guarda tudo que aconteceu em cada lead.",
    ),
    (
        "Inteligência",
        "<b>Meu ICP</b>: edita o que a IA sabe sobre seu negócio. "
        "<b>IA de Objeções</b>: treina respostas. "
        "<b>Brainy Chat</b>: pergunta qualquer coisa sobre sua base.",
    ),
    (
        "Configurações & Templates",
        "Em <b>Configurações</b> você troca chave de IA, e em "
        "<b>Templates de Mensagem</b> ajusta o que vai pro WhatsApp. "
        "Você pode ligar o modo <b>IA Full</b> que personaliza o "
        "<i>corpo inteiro</i> da mensagem por lead, usando o site dele.",
    ),
    (
        "Pronto! 🚀",
        "Vá em <b>Hoje</b> ou <b>Busca Inteligente</b> pra começar. "
        "Você pode rever esse tour em <b>Ajuda → Refazer tour</b>.",
    ),
]


class TourDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tour — Brainy Prospect")
        self.setModal(True)
        self.setMinimumSize(560, 340)
        self._idx = 0

        c = theme_colors()
        self.setStyleSheet(
            f"QDialog{{background:{c['panel']};color:{c['text']};}}"
            f"QLabel#tourTitle{{font-size:18pt;font-weight:700;color:{c['text']};}}"
            f"QLabel#tourBody{{font-size:11pt;color:{c['text']};line-height:140%;}}"
            f"QLabel#tourStep{{color:{c['text_dim']};font-size:9pt;}}"
            f"QPushButton{{background:{c['panel_alt']};color:{c['text']};"
            f"border:1px solid {c['border']};padding:8px 16px;border-radius:6px;}}"
            f"QPushButton:hover{{background:{c['hover']};}}"
            f"QPushButton#primary{{background:{c['accent']};color:white;border:none;}}"
            f"QPushButton#primary:hover{{background:{c['accent_hi']};}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        self.step_lbl = QLabel(); self.step_lbl.setObjectName("tourStep")
        self.title_lbl = QLabel(); self.title_lbl.setObjectName("tourTitle")
        self.title_lbl.setWordWrap(True)
        self.body_lbl = QLabel(); self.body_lbl.setObjectName("tourBody")
        self.body_lbl.setWordWrap(True)
        self.body_lbl.setTextFormat(Qt.RichText)

        lay.addWidget(self.step_lbl)
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.body_lbl, 1)

        btns = QHBoxLayout()
        self.skip_btn = QPushButton("Pular tour")
        self.skip_btn.clicked.connect(self.reject)
        self.back_btn = QPushButton("Voltar")
        self.back_btn.clicked.connect(self._back)
        self.next_btn = QPushButton("Próximo →")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._next)
        btns.addWidget(self.skip_btn)
        btns.addStretch(1)
        btns.addWidget(self.back_btn)
        btns.addWidget(self.next_btn)
        lay.addLayout(btns)

        self._render()

    def _render(self) -> None:
        title, body = _STEPS[self._idx]
        self.step_lbl.setText(f"Passo {self._idx + 1} de {len(_STEPS)}")
        self.title_lbl.setText(title)
        self.body_lbl.setText(body)
        self.back_btn.setEnabled(self._idx > 0)
        self.next_btn.setText("Concluir" if self._idx == len(_STEPS) - 1 else "Próximo →")

    def _next(self) -> None:
        if self._idx >= len(_STEPS) - 1:
            self.accept()
            return
        self._idx += 1
        self._render()

    def _back(self) -> None:
        if self._idx > 0:
            self._idx -= 1
            self._render()


def maybe_run(parent: QWidget | None = None, *, force: bool = False) -> None:
    s = QSettings("BrainyProspect", "BrainyProspect")
    if not force and s.value("app/tour_done", False, bool):
        return
    dlg = TourDialog(parent)
    dlg.exec()
    s.setValue("app/tour_done", True)
