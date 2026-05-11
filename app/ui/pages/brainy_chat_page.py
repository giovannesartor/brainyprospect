"""Brainy AI Assistant — chat interno usando DeepSeek/OpenAI com contexto dos leads."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadRepository


def _build_context_summary() -> str:
    """Resume o estado atual dos leads para alimentar a IA."""
    stats = LeadRepository.stats()
    pipe = LeadRepository.pipeline_stats()
    prio = LeadRepository.priority_distribution()
    hot = LeadRepository.query(min_score=80, limit=10)
    hot_lines = [
        f"  - {h['name']} ({h.get('city','')}) score {h.get('score',0)} "
        f"prio {h.get('priority','')} tipo {h.get('prospection_mode','')}"
        for h in hot
    ]
    return (
        f"Total leads: {stats['total']} | hoje: {stats['today']} | "
        f"avg score: {stats['avg_score']}\n"
        f"Diretos: {stats['direct_total']} | Parceiros: {stats['partners_total']}\n"
        f"Pipeline: {pipe}\n"
        f"Prioridade: {prio}\n"
        f"Top 10 leads quentes:\n" + "\n".join(hot_lines)
    )


class _AskWorker(QThread):
    finished_text = Signal(str)
    failed = Signal(str)

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def run(self) -> None:
        try:
            from app.services.ai.client import _build_client  # type: ignore[attr-defined]
            client, model, temperature, max_tokens = _build_client()
            ctx = _build_context_summary()
            sys_msg = (
                "Você é o Brainy AI, assistente comercial estratégico do app Brainy Prospect. "
                "Use o CONTEXTO DE LEADS abaixo para responder. Seja direto, objetivo, "
                "em PT-BR. Se a pergunta exigir dados ausentes, peça. Sugira ações práticas."
            )
            full = (
                f"CONTEXTO ATUAL DOS LEADS:\n{ctx}\n\nPERGUNTA DO USUÁRIO:\n{self.prompt}"
            )
            resp = client.chat.completions.create(
                model=model, temperature=temperature, max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": full},
                ],
            )
            text = resp.choices[0].message.content if resp.choices else ""
            self.finished_text.emit(text or "—")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class _Bubble(QFrame):
    def __init__(self, text: str, role: str) -> None:
        super().__init__()
        self.setObjectName("card")
        if role == "user":
            self.setStyleSheet(
                "QFrame{background:#1B2230;border:1px solid #2A2F40;border-radius:12px}"
            )
        else:
            self.setStyleSheet(
                "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #1A1F36,stop:1 #14181F);border:1px solid #2D3556;border-radius:12px}"
            )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        who = QLabel("Você" if role == "user" else "🧠 Brainy AI")
        from app.ui.theme import colors as _c
        _cc = _c()
        who.setStyleSheet(
            f"color:{_cc['text_dim']};font-size:10px;font-weight:700;letter-spacing:1.4px"
        )
        lay.addWidget(who)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setStyleSheet(f"color:{_cc['text']};font-size:13px;line-height:18px")
        lay.addWidget(body)


class BrainyChatPage(QWidget):
    """Chat estilo ChatGPT usando o provider configurado."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("🧠 Brainy AI Assistant")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch()
        sub = QLabel("Powered by DeepSeek / OpenAI · contexto dos seus leads")
        sub.setObjectName("mutedSmall")
        head.addWidget(sub)
        root.addLayout(head)

        # área scroll com bolhas
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        self.bubbles_lay = QVBoxLayout(container)
        self.bubbles_lay.setContentsMargins(0, 0, 0, 0)
        self.bubbles_lay.setSpacing(10)
        self.bubbles_lay.addStretch(1)
        self.scroll.setWidget(container)
        root.addWidget(self.scroll, 1)

        # sugestões rápidas
        chips_row = QHBoxLayout()
        for s in ("Quais leads devo abordar hoje?",
                  "Qual cidade tem mais oportunidade?",
                  "Resumo do meu pipeline",
                  "Como abordar parceiros premium?"):
            b = QPushButton(s)
            b.setObjectName("ghost")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=s: (self.input.setText(t), self._send()))
            chips_row.addWidget(b)
        chips_row.addStretch()
        root.addLayout(chips_row)

        # input
        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Pergunte algo ao Brainy AI…")
        self.input.returnPressed.connect(self._send)
        self.input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.send_btn = QPushButton("Enviar")
        self.send_btn.setObjectName("primary")
        self.send_btn.clicked.connect(self._send)
        bottom.addWidget(self.input, 1)
        bottom.addWidget(self.send_btn)
        root.addLayout(bottom)

        self._add_bubble(
            "Olá! Eu sou o Brainy AI. Posso analisar seu pipeline, sugerir leads "
            "para abordar hoje, recomendar abordagens e responder dúvidas comerciais. "
            "Faça uma pergunta para começar.",
            role="assistant",
        )

    def _add_bubble(self, text: str, role: str) -> None:
        bubble = _Bubble(text, role)
        # insere antes do stretch
        idx = self.bubbles_lay.count() - 1
        self.bubbles_lay.insertWidget(idx, bubble)
        # rola para o final
        self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum() + 999
        )

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._add_bubble(text, role="user")
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Pensando…")

        self._worker = _AskWorker(text)
        self._worker.finished_text.connect(self._on_response)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_response(self, text: str) -> None:
        self._add_bubble(text, role="assistant")
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Enviar")

    def _on_failed(self, err: str) -> None:
        self._add_bubble(
            f"⚠ Não consegui responder agora: {err}\n"
            "Verifique sua API key em Configurações.",
            role="assistant",
        )
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Enviar")
