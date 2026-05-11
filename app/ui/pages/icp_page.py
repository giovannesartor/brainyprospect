"""Página de perfil ICP do usuário + recomputar prioridade dos leads."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadRepository
from app.services import user_icp
from app.services.intelligence import compute_priority


class _RescoreWorker(QThread):
    progress_signal = Signal(int, int)
    done = Signal(int)

    def run(self) -> None:
        rows = LeadRepository.all_for_recompute()
        total = len(rows) or 1
        n = 0
        for i, r in enumerate(rows):
            try:
                signals = r.get("buying_signals") or []
                if not isinstance(signals, list):
                    signals = []
                ms = int(r.get("match_score") or 0)
                sc = int(r.get("score") or 0)
                prio = compute_priority(sc, ms, signals)
                LeadRepository.update_priority_score(int(r["id"]), ms, prio)
                n += 1
            except Exception:  # noqa: BLE001
                pass
            if i % 10 == 0:
                self.progress_signal.emit(i, total)
        self.progress_signal.emit(total, total)
        self.done.emit(n)


class ICPPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        scroll = QScrollArea(self); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        page = QWidget(); scroll.setWidget(page)
        root = QVBoxLayout(page); root.setContentsMargins(28, 24, 28, 24); root.setSpacing(16)

        title = QLabel("🎯  <b>Seu Perfil de Cliente Ideal (ICP)</b>")
        title.setStyleSheet("font-size:18px")
        root.addWidget(title)
        sub = QLabel("Esses dados alimentam a IA: melhoram match-score, recomendam "
                     "leads e geram respostas a objeções com seu contexto.")
        sub.setObjectName("muted"); sub.setWordWrap(True)
        root.addWidget(sub)

        card = QFrame(); card.setObjectName("sectionCard")
        cl = QVBoxLayout(card); cl.setContentsMargins(20, 16, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        d = user_icp.load()
        self.company_name = QLineEdit(d.get("company_name", ""))
        self.website = QLineEdit(d.get("website", ""))
        self.business_summary = QPlainTextEdit(d.get("business_summary", ""))
        self.business_summary.setMinimumHeight(80)
        self.ideal_client = QPlainTextEdit(d.get("ideal_client", ""))
        self.ideal_client.setMinimumHeight(80)
        self.differentials = QPlainTextEdit(d.get("differentials", ""))
        self.differentials.setMinimumHeight(60)
        self.avg_ticket = QLineEdit(d.get("avg_ticket", ""))
        form.addRow("Nome da empresa", self.company_name)
        form.addRow("Site da sua empresa", self.website)
        form.addRow("O que vendemos (em 2-3 linhas)", self.business_summary)
        form.addRow("Cliente ideal (quem é, dor, contexto)", self.ideal_client)
        form.addRow("Diferenciais", self.differentials)
        form.addRow("Ticket médio", self.avg_ticket)
        cl.addLayout(form)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        save_btn = QPushButton("💾  Salvar perfil"); save_btn.setObjectName("primary")
        save_btn.setMinimumHeight(40); save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        cl.addLayout(btn_row)
        root.addWidget(card)

        # Recompute
        rec_card = QFrame(); rec_card.setObjectName("sectionCard")
        rl = QVBoxLayout(rec_card); rl.setContentsMargins(20, 16, 20, 16); rl.setSpacing(8)
        rh = QLabel("⚙  Recomputar prioridade de todos os leads")
        rh.setStyleSheet("font-weight:700;font-size:14px")
        rl.addWidget(rh)
        rl.addWidget(QLabel("Quando você ajusta seu ICP, vale recalcular para refletir "
                            "as novas regras nos leads existentes."))
        self.progress = QProgressBar(); self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        rl.addWidget(self.progress)
        rb = QHBoxLayout(); rb.addStretch()
        self.rec_btn = QPushButton("🔄  Recomputar prioridades agora")
        self.rec_btn.clicked.connect(self._recompute)
        rb.addWidget(self.rec_btn)
        rl.addLayout(rb)
        root.addWidget(rec_card)

        root.addStretch()

    def _save(self) -> None:
        data = {
            "company_name": self.company_name.text().strip(),
            "website": self.website.text().strip(),
            "business_summary": self.business_summary.toPlainText().strip(),
            "ideal_client": self.ideal_client.toPlainText().strip(),
            "differentials": self.differentials.toPlainText().strip(),
            "avg_ticket": self.avg_ticket.text().strip(),
        }
        user_icp.save(data)
        QMessageBox.information(self, "Salvo", "Perfil ICP atualizado.")

    def _recompute(self) -> None:
        self.rec_btn.setEnabled(False); self.rec_btn.setText("Recalculando…")
        self.progress.setVisible(True); self.progress.setValue(0)
        self._w = _RescoreWorker()
        self._w.progress_signal.connect(
            lambda i, t: self.progress.setRange(0, t) or self.progress.setValue(i)
        )
        self._w.done.connect(self._on_done)
        self._w.start()

    def _on_done(self, n: int) -> None:
        self.rec_btn.setEnabled(True)
        self.rec_btn.setText("🔄  Recomputar prioridades agora")
        self.progress.setVisible(False)
        QMessageBox.information(self, "Pronto", f"{n} leads recomputados.")
