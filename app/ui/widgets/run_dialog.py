"""Diálogo modal para acompanhar execuções longas (prospecção, scraping, etc).

Mostra em tempo real:
- Etapa atual + percentual
- Log completo com timestamps e emojis por tipo
- Tempo decorrido (atualizado a cada segundo)
- Botões: Copiar log, Minimizar (fechar mantendo execução), Fechar
"""
from __future__ import annotations

import time
from typing import Any, Callable

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from app.ui.workers import Worker, run_in_thread


def _icon_for(msg: str) -> str:
    m = msg.lower()
    if any(w in m for w in ("erro", "fail", "falh", "✖")):
        return "✖"
    if any(w in m for w in ("✔", "concluí", "salv")):
        return "✔"
    if "ia" in m or "openai" in m or "deepseek" in m or "qualif" in m:
        return "🧠"
    if "scrap" in m or "site" in m or "html" in m:
        return "🌐"
    if "google" in m or "busca" in m or "search" in m:
        return "🔎"
    if "icp" in m or "anal" in m:
        return "🎯"
    if "salv" in m or "banco" in m:
        return "💾"
    if "modo" in m or "estratég" in m:
        return "⚙"
    return "›"


class ProspectionRunDialog(QDialog):
    """Diálogo modal que executa um worker em thread e exibe log ao vivo."""

    def __init__(self, parent, title: str, fn: Callable[..., Any], *args,
                 with_progress: bool = True, **kwargs) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # não bloqueia o resto da janela
        self.setMinimumSize(720, 520)
        self.resize(820, 600)
        # Mantém em cima
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)

        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._with_progress = with_progress
        self._result: Any = None
        self._error: str | None = None
        self._done = False
        self._start_ts = time.time()
        self._worker = None
        self._thread = None
        self._last_progress_ts = time.time()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # Cabeçalho
        head = QVBoxLayout(); head.setSpacing(2)
        title_lbl = QLabel(f"⚡  {title}")
        title_lbl.setStyleSheet("font-size:18px;font-weight:700")
        head.addWidget(title_lbl)
        self.status_lbl = QLabel("Inicializando…")
        self.status_lbl.setObjectName("muted")
        head.addWidget(self.status_lbl)
        root.addLayout(head)

        # Progresso + tempo
        prow = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100); self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setMinimumHeight(22)
        prow.addWidget(self.progress, 1)
        self.elapsed_lbl = QLabel("⏱ 00:00")
        from app.ui.theme import colors as _c
        _cc = _c()
        self.elapsed_lbl.setStyleSheet(
            f"color:{_cc['text']};font-weight:600;font-family:'SF Mono',Menlo,monospace;"
            "padding:0 6px"
        )
        prow.addWidget(self.elapsed_lbl)
        root.addLayout(prow)

        # Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Logs aparecerão aqui em tempo real…")
        mono = QFont("SF Mono")
        if not mono.exactMatch():
            mono = QFont("Menlo")
        mono.setPointSize(11)
        self.log.setFont(mono)
        self.log.setStyleSheet(
            f"QPlainTextEdit{{background:{_cc['panel_alt']};color:{_cc['text']};"
            f"border:1px solid {_cc['border']};border-radius:8px;padding:10px}}"
        )
        root.addWidget(self.log, 1)

        # Botões
        btns = QHBoxLayout()
        self.copy_btn = QPushButton("📋  Copiar log")
        self.copy_btn.setObjectName("ghost")
        self.copy_btn.clicked.connect(self._copy_log)
        btns.addWidget(self.copy_btn)

        self.min_btn = QPushButton("Minimizar")
        self.min_btn.setObjectName("ghost")
        self.min_btn.clicked.connect(self.hide)
        btns.addWidget(self.min_btn)

        btns.addStretch()
        self.close_btn = QPushButton("Fechar")
        self.close_btn.setObjectName("primary")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        btns.addWidget(self.close_btn)
        root.addLayout(btns)

        # Timer de tempo
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------ run
    def start(self) -> None:
        self._append("🚀  Iniciando…", level="info")
        # Defere para o próximo tick do event loop, garantindo que o show()
        # completou antes de criar a thread.
        QTimer.singleShot(0, self._spawn_worker)

    def _spawn_worker(self) -> None:
        try:
            self._worker = Worker(self._fn, *self._args,
                                  with_progress=self._with_progress, **self._kwargs)
            self._thread = run_in_thread(
                self, self._worker,
                on_finished=self._on_finished,
                on_failed=self._on_failed,
                on_progress=self._on_progress,
            )
            self._append("Thread iniciada — aguardando primeira resposta da IA…",
                         level="info")
        except Exception as e:  # noqa: BLE001
            import traceback
            tb = traceback.format_exc()
            self._on_failed(f"Falha ao iniciar thread: {e}\n{tb}")

    # ------------------------------------------------------------------ slots
    def _on_progress(self, msg: str, pct: int) -> None:
        self._last_progress_ts = time.time()
        self.progress.setValue(max(0, min(100, int(pct or 0))))
        self.status_lbl.setText(msg)
        self._append(msg, pct=pct)

    def _on_finished(self, result: Any) -> None:
        self._done = True
        self._result = result
        self.progress.setValue(100)
        self.status_lbl.setText("✔ Concluído")
        elapsed = self._fmt_elapsed()
        self._append(f"✔ Concluído em {elapsed}.", level="ok")
        # Resumo apropriado conforme tipo de resultado
        try:
            # AnalysisResult → mostra produtos detectados
            icp = getattr(result, "icp", None)
            has_leads_attr = hasattr(result, "leads")
            if icp is not None and not has_leads_attr:
                products = getattr(icp, "products", []) or []
                bt = getattr(icp, "business_type", "") or "—"
                self._append(f"🎯 Negócio: {bt}", level="ok")
                self._append(f"📦 {len(products)} produto(s) detectado(s).", level="ok")
                for p in products:
                    nm = p.get("name", "")
                    rec = p.get("recommended_mode", "") or "—"
                    self._append(f"   • {nm}  (sugere: {rec})")
            elif has_leads_attr:
                # HuntResult
                n = len(getattr(result, "leads", []) or [])
                d = getattr(result, "direct_count", None)
                p = getattr(result, "partners_count", None)
                extra = [f"{n} leads"]
                if d is not None:
                    extra.append(f"diretos={d}")
                if p is not None:
                    extra.append(f"parceiros={p}")
                self._append("📊  " + " · ".join(extra), level="ok")
        except Exception:  # noqa: BLE001
            pass
        self.close_btn.setEnabled(True)
        self.close_btn.setText("Fechar e ver leads")
        self.min_btn.setVisible(False)
        self._timer.stop()
        # se janela ainda visível, traz pra frente
        if self.isVisible():
            self.raise_()

    def _on_failed(self, err: str) -> None:
        self._done = True
        self._error = err
        self.status_lbl.setText("✖ Falhou")
        self._append(f"✖ Falhou: {err}", level="err")
        self.close_btn.setEnabled(True)
        self.close_btn.setText("Fechar")
        self.min_btn.setVisible(False)
        self._timer.stop()
        if not self.isVisible():
            self.show(); self.raise_()
        QMessageBox.critical(self, "Erro", err)

    # ------------------------------------------------------------------ utils
    def _tick(self) -> None:
        self.elapsed_lbl.setText(f"⏱ {self._fmt_elapsed()}")
        # Heartbeat: se nada há mais de 20s, alerta o usuário
        silent = int(time.time() - self._last_progress_ts)
        if silent in (20, 60, 120) and not self._done:
            self._append(
                f"⚠  Sem novas mensagens há {silent}s. "
                "Pode ser scraping/IA lento, ou rede travada. "
                "Confira sua chave OpenAI/DeepSeek em Configurações.",
                level="err",
            )

    def _fmt_elapsed(self) -> str:
        s = int(time.time() - self._start_ts)
        m, sec = divmod(s, 60)
        return f"{m:02d}:{sec:02d}"

    def _append(self, msg: str, pct: int | None = None, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        icon = "✔" if level == "ok" else ("✖" if level == "err" else _icon_for(msg))
        # remove icones duplicados se já estão no msg
        clean = msg
        for prefix in ("✔ ", "✖ ", "🚀 "):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
        pct_txt = f"[{pct:>3}%] " if pct is not None else "       "
        line = f"[{ts}] {pct_txt}{icon}  {clean}"
        self.log.appendPlainText(line)
        # auto-scroll
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log.setTextCursor(cursor)

    def _copy_log(self) -> None:
        QGuiApplication.clipboard().setText(self.log.toPlainText())
        self.status_lbl.setText("📋 Log copiado para a área de transferência")

    # ------------------------------------------------------------------ public
    @property
    def result(self) -> Any:
        return self._result

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def is_done(self) -> bool:
        return self._done

    def closeEvent(self, ev) -> None:
        # se ainda rodando e usuário fecha, apenas esconde
        if not self._done:
            ev.ignore()
            self.hide()
            return
        super().closeEvent(ev)
