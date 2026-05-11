"""Monitoramento de empresas — watch-list + execução manual de re-scrape."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadRepository, WatchRepository
from app.services.monitoring import run_all_now
from app.utils.notifications import notify


class _RunWorker(QThread):
    progress_signal = Signal(str, int)
    done = Signal(int)
    fail = Signal(str)

    def run(self) -> None:
        try:
            n = run_all_now(progress=self.progress_signal.emit)
            self.done.emit(n)
        except Exception as e:  # noqa: BLE001
            self.fail.emit(str(e))


class MonitoringPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24); root.setSpacing(14)

        intro = QLabel(
            "📡  <b>Monitoramento</b> — adicione empresas à sua watch-list. "
            "O Brainy faz re-scrape periódico e te avisa quando algo muda "
            "(conteúdo, título, novos sinais comerciais)."
        )
        intro.setObjectName("intro"); intro.setWordWrap(True)
        root.addWidget(intro)

        # Toolbar
        bar = QHBoxLayout()
        self.add_lead_btn = QPushButton("➕ Adicionar lead à watch-list")
        self.add_lead_btn.clicked.connect(self._add_from_lead)
        self.add_url_btn = QPushButton("🌐 Adicionar URL avulsa")
        self.add_url_btn.clicked.connect(self._add_url)
        self.run_btn = QPushButton("⚡ Verificar agora")
        self.run_btn.setObjectName("primary")
        self.run_btn.clicked.connect(self._run_now)
        self.refresh_btn = QPushButton("Recarregar")
        self.refresh_btn.setObjectName("ghost")
        self.refresh_btn.clicked.connect(self.reload)
        for b in (self.add_lead_btn, self.add_url_btn, self.run_btn):
            bar.addWidget(b)
        bar.addStretch()
        bar.addWidget(self.refresh_btn)
        root.addLayout(bar)

        self.status = QLabel("")
        self.status.setObjectName("mutedSmall")
        root.addWidget(self.status)

        # Splitter: watch-list + eventos
        sp = QSplitter(Qt.Vertical)

        wl_card = QFrame(); wl_card.setObjectName("sectionCard")
        wll = QVBoxLayout(wl_card); wll.setContentsMargins(16, 12, 16, 12)
        wll.addWidget(QLabel("Empresas monitoradas"))
        self.watch_table = QTableWidget(0, 6)
        self.watch_table.setHorizontalHeaderLabels(
            ["Nome", "Site", "Última verificação", "Última mudança", "Intervalo (d)", "Ações"]
        )
        self.watch_table.verticalHeader().setVisible(False)
        self.watch_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        wll.addWidget(self.watch_table, 1)
        sp.addWidget(wl_card)

        ev_card = QFrame(); ev_card.setObjectName("sectionCard")
        evl = QVBoxLayout(ev_card); evl.setContentsMargins(16, 12, 16, 12)
        evl.addWidget(QLabel("Mudanças recentes"))
        self.events_table = QTableWidget(0, 4)
        self.events_table.setHorizontalHeaderLabels(
            ["Quando", "Empresa", "Tipo", "Resumo"]
        )
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        evl.addWidget(self.events_table, 1)
        sp.addWidget(ev_card)
        sp.setSizes([420, 280])
        root.addWidget(sp, 1)

        self.reload()

    def reload(self) -> None:
        items = WatchRepository.list_all()
        self.watch_table.setRowCount(0)
        for w in items:
            r = self.watch_table.rowCount()
            self.watch_table.insertRow(r)
            self.watch_table.setItem(r, 0, QTableWidgetItem(w["name"]))
            self.watch_table.setItem(r, 1, QTableWidgetItem(w["website"]))
            lc = w["last_checked_at"].strftime("%d/%m %H:%M") if w["last_checked_at"] else "—"
            ch = w["last_change_at"].strftime("%d/%m %H:%M") if w["last_change_at"] else "—"
            self.watch_table.setItem(r, 2, QTableWidgetItem(lc))
            self.watch_table.setItem(r, 3, QTableWidgetItem(ch))
            self.watch_table.setItem(r, 4, QTableWidgetItem(str(w["interval_days"])))
            rm = QPushButton("Remover")
            rm.clicked.connect(lambda _=False, wid=w["id"]: self._remove(wid))
            self.watch_table.setCellWidget(r, 5, rm)
        self.status.setText(f"{len(items)} empresas monitoradas.")

        evs = WatchRepository.recent_events(80)
        self.events_table.setRowCount(0)
        for e in evs:
            r = self.events_table.rowCount()
            self.events_table.insertRow(r)
            ts = e["detected_at"].strftime("%d/%m %H:%M")
            self.events_table.setItem(r, 0, QTableWidgetItem(ts))
            self.events_table.setItem(r, 1, QTableWidgetItem(e["name"]))
            self.events_table.setItem(r, 2, QTableWidgetItem(e["kind"]))
            self.events_table.setItem(r, 3, QTableWidgetItem(e["summary"]))

    def _add_url(self) -> None:
        url, ok = QInputDialog.getText(self, "Adicionar URL",
                                       "URL do site a monitorar:")
        if not ok or not url.strip():
            return
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        name, ok2 = QInputDialog.getText(self, "Nome", "Nome / apelido da empresa:")
        if not ok2 or not name.strip():
            name = url
        days, ok3 = QInputDialog.getInt(self, "Intervalo",
                                        "Verificar a cada quantos dias?", 7, 1, 90)
        if not ok3:
            days = 7
        WatchRepository.add(name=name.strip(), website=url, interval_days=days)
        self.reload()

    def _add_from_lead(self) -> None:
        rows = LeadRepository.query(limit=2000)
        with_site = [r for r in rows if r.get("website")]
        if not with_site:
            QMessageBox.information(self, "Sem leads",
                                    "Nenhum lead com site cadastrado.")
            return
        items = [f"{r['name']} — {r['website']}" for r in with_site]
        item, ok = QInputDialog.getItem(
            self, "Adicionar à watch-list", "Escolha o lead:", items, 0, False
        )
        if not ok:
            return
        idx = items.index(item)
        lead = with_site[idx]
        WatchRepository.add(
            name=lead["name"], website=lead["website"], lead_id=lead["id"],
        )
        self.reload()

    def _remove(self, wid: int) -> None:
        WatchRepository.remove(wid); self.reload()

    def _run_now(self) -> None:
        if self.watch_table.rowCount() == 0:
            QMessageBox.information(self, "Vazio",
                                    "Adicione empresas à watch-list primeiro.")
            return
        self.run_btn.setEnabled(False); self.run_btn.setText("Verificando…")
        self._worker = _RunWorker()
        self._worker.progress_signal.connect(
            lambda m, p: self.status.setText(f"[{p}%] {m}")
        )
        self._worker.done.connect(self._on_done)
        self._worker.fail.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, n: int) -> None:
        self.run_btn.setEnabled(True); self.run_btn.setText("⚡ Verificar agora")
        self.reload()
        if n > 0:
            notify("Brainy Prospect — Mudanças detectadas",
                   f"{n} empresa(s) tiveram mudanças relevantes.")
        QMessageBox.information(self, "Concluído",
                                f"Verificação finalizada. {n} mudança(s) detectada(s).")

    def _on_fail(self, msg: str) -> None:
        self.run_btn.setEnabled(True); self.run_btn.setText("⚡ Verificar agora")
        QMessageBox.critical(self, "Falha", msg)
