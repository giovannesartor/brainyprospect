"""IA de Objeções — cole a objeção, receba 3 respostas consultivas."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.database import ObjectionRepository
from app.services.user_icp import summary_for_ai


SYSTEM = (
    "Você é um especialista em vendas consultivas B2B no Brasil. "
    "Quebra objeções com tom natural, empático e direto. "
    "Sempre devolva exatamente 3 respostas em JSON, com este formato: "
    '{"responses":[{"approach":"empática","text":"..."},'
    '{"approach":"consultiva","text":"..."},'
    '{"approach":"provocativa","text":"..."}]}. '
    "Cada texto: 2 a 4 linhas, em PT-BR. Nada além do JSON."
)


class _AskWorker(QThread):
    done = Signal(list)
    fail = Signal(str)

    def __init__(self, objection: str, context: str) -> None:
        super().__init__()
        self.objection = objection; self.context = context

    def run(self) -> None:
        try:
            from app.services.ai.client import _build_client
            import json as _json
            client, model, temperature, max_tokens = _build_client()
            user = (
                f"CONTEXTO DO MEU NEGÓCIO:\n{self.context or '—'}\n\n"
                f"OBJEÇÃO RECEBIDA:\n{self.objection}\n\n"
                "Gere 3 respostas (empática, consultiva, provocativa) em JSON."
            )
            resp = client.chat.completions.create(
                model=model, temperature=0.7, max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content if resp.choices else "{}"
            data = _json.loads(text)
            items = data.get("responses") or []
            if not isinstance(items, list):
                items = []
            self.done.emit(items)
        except Exception as e:  # noqa: BLE001
            self.fail.emit(str(e))


class ObjectionsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24); outer.setSpacing(16)

        intro = QLabel(
            "🛡  <b>IA de Objeções</b> — cole a objeção do prospect e receba "
            "3 respostas com tons diferentes (empática, consultiva, provocativa)."
        )
        intro.setObjectName("intro"); intro.setWordWrap(True)
        outer.addWidget(intro)

        splitter = QSplitter(Qt.Horizontal)

        # Esquerda: input + resultados
        left = QWidget(); ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(10)

        in_card = QFrame(); in_card.setObjectName("sectionCard")
        il = QVBoxLayout(in_card); il.setContentsMargins(18, 14, 18, 14); il.setSpacing(8)
        h = QLabel("Objeção do cliente"); h.setObjectName("sectionHead"); il.addWidget(h)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Ex.: 'Achei caro', 'Já tenho fornecedor', 'Não temos budget agora', "
            "'Preciso pensar', 'Mande email que avalio'…"
        )
        self.input.setMinimumHeight(110)
        il.addWidget(self.input)
        row = QHBoxLayout(); row.addStretch()
        self.go_btn = QPushButton("⚡  Quebrar objeção")
        self.go_btn.setObjectName("primary"); self.go_btn.setMinimumWidth(200)
        self.go_btn.setMinimumHeight(40)
        self.go_btn.clicked.connect(self._ask)
        row.addWidget(self.go_btn)
        il.addLayout(row)
        ll.addWidget(in_card)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.NoFrame)
        self.results_box = QWidget()
        self.results_layout = QVBoxLayout(self.results_box)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(10)
        self.results_layout.addStretch()
        self.results_scroll.setWidget(self.results_box)
        ll.addWidget(self.results_scroll, 1)

        splitter.addWidget(left)

        # Direita: histórico
        right = QFrame(); right.setObjectName("sectionCard")
        rl = QVBoxLayout(right); rl.setContentsMargins(16, 14, 16, 14); rl.setSpacing(6)
        rh = QLabel("Histórico"); rh.setObjectName("sectionHead"); rl.addWidget(rh)
        self.history = QListWidget()
        self.history.itemClicked.connect(self._reload_from_history)
        rl.addWidget(self.history, 1)
        splitter.addWidget(right)
        splitter.setSizes([900, 360])
        outer.addWidget(splitter, 1)

        self.reload_history()

    # ---------------- ações
    def _ask(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Atenção", "Cole a objeção primeiro.")
            return
        self.go_btn.setEnabled(False); self.go_btn.setText("Pensando…")
        self._render_results([])
        self._worker = _AskWorker(text, summary_for_ai())
        self._worker.done.connect(lambda items: self._on_done(text, items))
        self._worker.fail.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, objection: str, items: list[dict]) -> None:
        self.go_btn.setEnabled(True); self.go_btn.setText("⚡  Quebrar objeção")
        if not items:
            QMessageBox.warning(self, "Vazio", "A IA não retornou respostas.")
            return
        ObjectionRepository.create(objection, items, summary_for_ai())
        self._render_results(items)
        self.reload_history()

    def _on_fail(self, err: str) -> None:
        self.go_btn.setEnabled(True); self.go_btn.setText("⚡  Quebrar objeção")
        QMessageBox.critical(self, "Erro IA",
                             f"{err}\n\nVerifique sua API key em Configurações.")

    def _render_results(self, items: list[dict]) -> None:
        # limpa
        while self.results_layout.count() > 1:
            it = self.results_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        colors_map = {"empática": "#10B981", "consultiva": "#6366F1",
                      "provocativa": "#F59E0B"}
        for it in items:
            approach = (it.get("approach") or "").lower()
            color = colors_map.get(approach, "#6366F1")
            card = QFrame(); card.setObjectName("card")
            card.setStyleSheet(
                f"QFrame#card{{border-left:4px solid {color};border-radius:10px}}"
            )
            cl = QVBoxLayout(card); cl.setContentsMargins(16, 12, 16, 14)
            head = QLabel(approach.capitalize() or "Resposta")
            head.setStyleSheet(f"color:{color};font-weight:700;font-size:11px;"
                               "letter-spacing:1.2px;text-transform:uppercase")
            cl.addWidget(head)
            body = QLabel(it.get("text") or "")
            body.setWordWrap(True); body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.setStyleSheet("font-size:13px;line-height:18px")
            cl.addWidget(body)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

    def reload_history(self) -> None:
        self.history.clear()
        for h in ObjectionRepository.list_recent(40):
            ts = h["created_at"].strftime("%d/%m %H:%M")
            txt = h["objection_text"][:60].replace("\n", " ")
            item = QListWidgetItem(f"[{ts}] {txt}")
            item.setData(Qt.UserRole, h)
            self.history.addItem(item)

    def _reload_from_history(self, item: QListWidgetItem) -> None:
        h = item.data(Qt.UserRole)
        if not h:
            return
        self.input.setPlainText(h["objection_text"])
        self._render_results(h.get("responses") or [])
