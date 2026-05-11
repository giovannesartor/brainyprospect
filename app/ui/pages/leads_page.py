"""Tela de Leads (tabela com filtros, exportação, detalhe)."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSettings, QSize, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import (
    CampaignRepository,
    LeadInteractionRepository,
    LeadRepository,
    WatchRepository,
)
from app.services import export_csv, export_json, export_xlsx
from app.services.intelligence import PRIORITY_LABEL
from app.utils.contact import best_contact_phone, mailto_link, whatsapp_link

COLUMNS = [
    ("priority", "Prioridade"),
    ("name", "Nome"),
    ("prospection_mode", "Tipo"),
    ("niche", "Nicho"),
    ("city", "Cidade"),
    ("state", "UF"),
    ("phone", "Telefone"),
    ("whatsapp", "WhatsApp"),
    ("email", "Email"),
    ("website", "Site"),
    ("score", "Score"),
    ("match_score", "Match"),
    ("ticket_estimate", "Ticket"),
    ("tags", "Tags"),
    ("status", "Status"),
]

MODE_LABEL = {"direct_sale": "Venda Direta", "partners": "Parceiro"}
STATUS_LIST = ["novo", "qualificado", "contatado", "respondeu",
               "reuniao", "proposta", "fechado", "perdido"]


class LeadsModel(QAbstractTableModel):
    def __init__(self, rows: list[dict] | None = None) -> None:
        super().__init__()
        self._rows = rows or []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return COLUMNS[section][1]
        return section + 1

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = COLUMNS[index.column()][0]
        val = row.get(key, "")
        if role == Qt.DisplayRole:
            if key == "score" or key == "match_score":
                return f"{int(val or 0)}"
            if key == "prospection_mode":
                return MODE_LABEL.get(str(val or ""), "—")
            if key == "priority":
                return PRIORITY_LABEL.get(str(val or "media"), ("—", ""))[0]
            if val is None:
                return ""
            return str(val)
        if role == Qt.ForegroundRole and key in ("score", "match_score"):
            try:
                v = int(val or 0)
            except Exception:
                v = 0
            if v >= 80:
                return QColor("#34D399")
            if v >= 50:
                return QColor("#FBBF24")
            return QColor("#9CA3AF")
        if role == Qt.ForegroundRole and key == "prospection_mode":
            return QColor("#22D3EE") if val == "partners" else QColor("#A78BFA")
        if role == Qt.ForegroundRole and key == "priority":
            return QColor(PRIORITY_LABEL.get(str(val or "media"), ("", "#9CA3AF"))[1])
        if role == Qt.TextAlignmentRole and key in ("score", "match_score"):
            return Qt.AlignCenter
        return None

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, idx: int) -> dict | None:
        return self._rows[idx] if 0 <= idx < len(self._rows) else None


class LeadsPage(QWidget):
    leads_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("BrainyProspect", "BrainyProspect")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        # Filtros
        filters = QFrame()
        filters.setObjectName("card")
        fl = QHBoxLayout(filters)
        fl.setContentsMargins(14, 12, 14, 12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pesquisar por nome, email, nicho, cidade…")
        self.search_input.returnPressed.connect(self.reload)
        self.mode_filter = QComboBox()
        self.mode_filter.addItem("Todos os tipos", "")
        self.mode_filter.addItem("Apenas Venda Direta", "direct_sale")
        self.mode_filter.addItem("Apenas Parceiros", "partners")
        self.priority_filter = QComboBox()
        self.priority_filter.addItem("Todas as prioridades", "")
        self.priority_filter.addItem("🔥 Máxima", "maxima")
        self.priority_filter.addItem("⚡ Alta", "alta")
        self.priority_filter.addItem("🟡 Média", "media")
        self.priority_filter.addItem("⚪ Baixa", "baixa")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos status", "")
        for st in STATUS_LIST:
            self.status_filter.addItem(st.capitalize(), st)
        self.city_input = QLineEdit(); self.city_input.setPlaceholderText("Cidade")
        self.state_input = QLineEdit(); self.state_input.setPlaceholderText("UF"); self.state_input.setMaximumWidth(70)
        self.niche_input = QLineEdit(); self.niche_input.setPlaceholderText("Nicho")
        self.min_score = QSpinBox(); self.min_score.setRange(0, 100); self.min_score.setPrefix("Score ≥ ")
        self.with_email_chk = QCheckBox("c/ Email")
        self.with_wa_chk = QCheckBox("c/ WhatsApp")
        self.no_site_chk = QCheckBox("s/ Site")

        self.apply_btn = QPushButton("Filtrar")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self.reload)

        for w in (self.search_input, self.city_input, self.state_input, self.niche_input,
                  self.min_score, self.mode_filter, self.priority_filter, self.status_filter,
                  self.with_email_chk, self.with_wa_chk, self.no_site_chk, self.apply_btn):
            fl.addWidget(w)
        root.addWidget(filters)

        # ---------- Toolbar de ações em massa ----------
        bulk_bar = QFrame(); bulk_bar.setObjectName("card")
        bb = QHBoxLayout(bulk_bar); bb.setContentsMargins(14, 10, 14, 10); bb.setSpacing(8)
        self.sel_lbl = QLabel("0 selecionados")
        self.sel_lbl.setObjectName("mutedHint")
        bb.addWidget(self.sel_lbl)
        bb.addSpacing(10)

        self.bulk_status = QComboBox(); self.bulk_status.addItem("Mudar status para…", "")
        for st in STATUS_LIST:
            self.bulk_status.addItem(st.capitalize(), st)
        self.bulk_status.activated.connect(self._bulk_status)
        bb.addWidget(self.bulk_status)

        self.bulk_campaign = QComboBox(); self.bulk_campaign.addItem("Atribuir à campanha…", -1)
        self.bulk_campaign.activated.connect(self._bulk_campaign)
        bb.addWidget(self.bulk_campaign)

        self.bulk_watch_btn = QPushButton("📡 Monitorar")
        self.bulk_watch_btn.clicked.connect(self._bulk_watch)
        bb.addWidget(self.bulk_watch_btn)

        self.bulk_export_btn = QPushButton("📤 Exportar selecionados")
        self.bulk_export_btn.clicked.connect(lambda: self._export("xlsx", only_selected=True))
        bb.addWidget(self.bulk_export_btn)

        self.bulk_delete_btn = QPushButton("🗑 Excluir")
        self.bulk_delete_btn.setObjectName("danger")
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        bb.addWidget(self.bulk_delete_btn)
        self.wipe_btn = QPushButton("🧹 Limpar tudo")
        self.wipe_btn.setObjectName("danger")
        self.wipe_btn.setToolTip("Apaga TODOS os leads, interações e histórico de buscas.")
        self.wipe_btn.clicked.connect(self._wipe_all)
        bb.addWidget(self.wipe_btn)
        bb.addStretch()
        self.import_btn = QPushButton("📥 Importar CSV/XLSX")
        self.import_btn.setObjectName("primary")
        self.import_btn.clicked.connect(self._open_import)
        bb.addWidget(self.import_btn)
        root.addWidget(bulk_bar)

        # Tabela + detalhes (splitter)
        splitter = QSplitter(Qt.Horizontal)

        self.model = LeadsModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().sectionMoved.connect(self._save_columns)
        self.table.clicked.connect(self._on_row_clicked)
        splitter.addWidget(self.table)
        # Painel de detalhe
        detail = QFrame()
        detail.setObjectName("card")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(16, 14, 16, 14)

        head = QHBoxLayout()
        head.addWidget(QLabel("Detalhes do Lead"))
        head.addStretch()
        self.copy_msg_btn = QPushButton("📋 Copiar msg")
        self.copy_msg_btn.setObjectName("ghost")
        self.copy_msg_btn.setEnabled(False)
        self.copy_msg_btn.clicked.connect(lambda: self._copy_message("a"))
        self.copy_msg_b_btn = QPushButton("📋 B")
        self.copy_msg_b_btn.setObjectName("ghost")
        self.copy_msg_b_btn.setEnabled(False)
        self.copy_msg_b_btn.clicked.connect(lambda: self._copy_message("b"))
        self.contact_wa = QPushButton("💬 WhatsApp")
        self.contact_wa.setObjectName("primary")
        self.contact_wa.setEnabled(False)
        self.contact_wa.clicked.connect(self._open_whatsapp)
        self.contact_email = QPushButton("✉ Email")
        self.contact_email.setEnabled(False)
        self.contact_email.clicked.connect(self._open_email)
        self.contact_site = QPushButton("🌐 Site")
        self.contact_site.setObjectName("ghost")
        self.contact_site.setEnabled(False)
        self.contact_site.clicked.connect(self._open_site)
        self.mark_sent_btn = QPushButton("✓ Marcar enviado")
        self.mark_sent_btn.setObjectName("ghost")
        self.mark_sent_btn.setEnabled(False)
        self.mark_sent_btn.clicked.connect(self._mark_sent)
        self.regen_btn = QPushButton("✨ Regerar IA")
        self.regen_btn.setObjectName("ghost")
        self.regen_btn.setEnabled(False)
        self.regen_btn.setToolTip("Gera abertura personalizada via IA (5-10s)")
        self.regen_btn.clicked.connect(self._regen_ai_message)
        head.addWidget(self.copy_msg_btn)
        head.addWidget(self.copy_msg_b_btn)
        head.addWidget(self.contact_wa)
        head.addWidget(self.contact_email)
        head.addWidget(self.contact_site)
        head.addWidget(self.regen_btn)
        head.addWidget(self.mark_sent_btn)
        dl.addLayout(head)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self._apply_detail_style()
        dl.addWidget(self.detail_view, 1)
        splitter.addWidget(detail)
        splitter.setSizes([900, 380])
        root.addWidget(splitter, 1)

        # Ações
        actions = QHBoxLayout()
        self.count_lbl = QLabel("0 leads")
        actions.addWidget(self.count_lbl)
        actions.addStretch()
        self.export_csv_btn = QPushButton("Exportar CSV")
        self.export_xlsx_btn = QPushButton("Exportar XLSX")
        self.export_xlsx_btn.setObjectName("primary")
        self.export_json_btn = QPushButton("Exportar JSON")
        self.export_csv_btn.clicked.connect(lambda: self._export("csv"))
        self.export_xlsx_btn.clicked.connect(lambda: self._export("xlsx"))
        self.export_json_btn.clicked.connect(lambda: self._export("json"))
        for b in (self.export_csv_btn, self.export_xlsx_btn, self.export_json_btn):
            actions.addWidget(b)
        root.addLayout(actions)

        self._current_lead: dict | None = None
        self.reload()
        self._restore_columns()
        self._refresh_campaigns()

        # Re-renderiza o detalhe quando o tema mudar (corrige cores hardcoded)
        try:
            from app.ui.theme import on_theme_changed
            on_theme_changed(self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, _theme: str) -> None:
        self._apply_detail_style()
        if self._current_lead:
            try:
                self.detail_view.setHtml(self._render_detail(self._current_lead))
            except Exception:
                pass

    def _apply_detail_style(self) -> None:
        from app.ui.theme import colors as theme_colors
        c = theme_colors()
        self.detail_view.setStyleSheet(
            f"QTextEdit{{background:{c['panel']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:8px;padding:10px;"
            f"selection-background-color:{c['accent']}}}"
        )

    # ---------- API ----------
    def reload(self) -> None:
        rows = LeadRepository.query(
            text=self.search_input.text().strip(),
            city=self.city_input.text().strip() or None,
            state=self.state_input.text().strip() or None,
            niche=self.niche_input.text().strip() or None,
            min_score=self.min_score.value(),
            only_with_email=self.with_email_chk.isChecked(),
            only_with_whatsapp=self.with_wa_chk.isChecked(),
            only_without_site=self.no_site_chk.isChecked(),
            prospection_mode=self.mode_filter.currentData() or None,
            priority=self.priority_filter.currentData() or None,
            status=self.status_filter.currentData() or None,
            limit=2000,
        )
        self.model.set_rows(rows)
        self.count_lbl.setText(f"{len(rows)} leads")
        self.table.resizeColumnsToContents()

    def _selected_rows(self) -> list[dict]:
        rows: list[dict] = []
        for idx in self.table.selectionModel().selectedRows():
            row = self.model.row_at(idx.row())
            if row:
                rows.append(row)
        return rows

    def _on_row_clicked(self, index: QModelIndex) -> None:
        row = self.model.row_at(index.row())
        if not row:
            return
        full = LeadRepository.get(int(row["id"])) or row
        self._current_lead = full
        html = self._render_detail(full)
        self.detail_view.setHtml(html)
        self.contact_wa.setEnabled(bool(best_contact_phone(full)))
        self.contact_email.setEnabled(bool(full.get("email")))
        self.contact_site.setEnabled(bool(full.get("website")))
        has_msg = bool((full.get("message_a") or "").strip())
        has_msg_b = bool((full.get("message_b") or "").strip())
        self.copy_msg_btn.setEnabled(has_msg)
        self.copy_msg_b_btn.setEnabled(has_msg_b)
        self.mark_sent_btn.setEnabled(has_msg or bool(full.get("phone") or full.get("email")))
        self.regen_btn.setEnabled(True)
        n = len(self._selected_rows())
        self.sel_lbl.setText(f"{n} selecionado(s)")

    def _render_detail(self, r: dict) -> str:
        from app.ui.theme import colors
        c = colors()
        TXT = c["text"]; H = c["header_title"]; DIM = c["text_dim"]; MUT = c["text_mute"]
        BG = c["bg"]; PANEL_ALT = c["panel_alt"]; BRD = c["border"]

        def li(label, value):
            value = value if (value not in (None, "", 0)) else "—"
            return (f"<tr><td style='color:{DIM};padding:4px 10px 4px 0'>{label}</td>"
                    f"<td style='color:{TXT}'>{value}</td></tr>")

        score = int(r.get("score") or 0)
        match = int(r.get("match_score") or 0)
        color = "#34D399" if score >= 80 else ("#FBBF24" if score >= 50 else "#9CA3AF")
        match_color = "#34D399" if match >= 80 else ("#FBBF24" if match >= 50 else "#9CA3AF")
        mode_label = MODE_LABEL.get(r.get("prospection_mode", ""), "—")
        mode_color = "#22D3EE" if r.get("prospection_mode") == "partners" else "#A78BFA"
        prio_label, prio_color = PRIORITY_LABEL.get(r.get("priority") or "media",
                                                    ("Média", "#FBBF24"))

        def chip(text, bg=PANEL_ALT, color=TXT, border=BRD):
            return (f"<span style='background:{bg};color:{color};border:1px solid {border};"
                    f"padding:3px 8px;border-radius:10px;margin-right:4px;font-size:11px'>"
                    f"{text}</span>")

        tags_html = ""
        if r.get("tags"):
            chips = [t.strip() for t in str(r["tags"]).split(",") if t.strip()]
            tags_html = " ".join(chip(c) for c in chips)

        signals_html = ""
        if r.get("buying_signals"):
            sig = r["buying_signals"] if isinstance(r["buying_signals"], list) else []
            signals_html = " ".join(
                chip(s, bg="#3B1A1A", color="#FCA5A5", border="#7F1D1D") for s in sig
            )

        techs_html = ""
        if r.get("technologies"):
            ts = [t.strip() for t in str(r["technologies"]).split(",") if t.strip()]
            techs_html = " ".join(
                chip(t, bg="#0F2638", color="#7DD3FC", border="#155E75") for t in ts
            )

        decisors_html = "—"
        if r.get("decision_makers"):
            dm = r["decision_makers"] if isinstance(r["decision_makers"], list) else []
            decisors_html = "<br>".join(
                f"<b>{d.get('name','')}</b> <span style='color:#8A93A6'>· {d.get('role','')}</span>"
                for d in dm
            ) or "—"

        # ---- E2 status badge ----
        status_map = {
            "nao_enviado": ("Não enviado", "#374151"),
            "enviado": ("Enviado", "#2563EB"),
            "respondido": ("Respondido", "#10B981"),
            "fechado": ("Fechado ✅", "#059669"),
            "perdido": ("Perdido", "#7F1D1D"),
        }
        st_label, st_color = status_map.get(r.get("send_status") or "nao_enviado",
                                            ("Não enviado", "#374151"))
        hot = int(r.get("hot_score") or 0)
        hot_color = "#EF4444" if hot >= 70 else ("#F59E0B" if hot >= 40 else "#6B7280")

        # ---- E1 mensagem pronta ----
        msg_a = (r.get("message_a") or "").strip()
        msg_b = (r.get("message_b") or "").strip()
        opener = (r.get("message_opener") or "").strip()
        tone = (r.get("message_tone") or "").strip()

        MSG_BG = c["panel_alt"]
        if msg_a:
            msg_card = f"""
            <div style="background:{MSG_BG};border:1px solid #2563EB;border-radius:10px;
                        padding:12px 14px;margin-bottom:14px">
              <div style="color:#2563EB;font-weight:700;font-size:13px;margin-bottom:6px">
                ✉ Mensagem pronta para enviar (versão A — {tone or "auto"})
              </div>
              <pre style="color:{TXT};white-space:pre-wrap;font-family:-apple-system;
                          font-size:12px;margin:0">{msg_a}</pre>
            </div>"""
            if msg_b:
                msg_card += f"""
            <div style="background:{MSG_BG};border:1px solid #7C3AED;border-radius:10px;
                        padding:12px 14px;margin-bottom:14px">
              <div style="color:#7C3AED;font-weight:700;font-size:13px;margin-bottom:6px">
                ✉ Versão B (variante A/B — teste qual converte melhor)
              </div>
              <pre style="color:{TXT};white-space:pre-wrap;font-family:-apple-system;
                          font-size:12px;margin:0">{msg_b}</pre>
            </div>"""
        else:
            msg_card = (f"<div style='color:{MUT};padding:10px;background:{MSG_BG};"
                        f"border:1px dashed {BRD};border-radius:8px;margin-bottom:14px'>"
                        "Mensagem ainda não gerada. Use 'Regerar mensagens' para criar.</div>")

        # ---- E3 histórico ----
        history_html = f"<p style='color:{MUT}'>Sem interações registradas.</p>"
        try:
            interactions = LeadInteractionRepository.list_for_lead(int(r.get("id") or 0))
        except Exception:
            interactions = []
        if interactions:
            kind_labels = {
                "whatsapp_sent": ("💬", "WhatsApp aberto", "#10B981"),
                "email_sent": ("✉", "Email aberto", "#2563EB"),
                "marked_sent": ("✓", "Marcado como enviado", "#0EA5E9"),
                "note": ("📝", "Nota", "#9CA3AF"),
                "status_change": ("🔁", "Status alterado", "#A78BFA"),
                "followup_sent": ("⏰", "Follow-up enviado", "#F59E0B"),
                "replied": ("📥", "Resposta recebida", "#34D399"),
            }
            items = []
            for it in interactions:
                ic, lab, c = kind_labels.get(it["kind"], ("•", it["kind"], "#9CA3AF"))
                ts = it["created_at"]
                ts_str = ts.strftime("%d/%m %H:%M") if hasattr(ts, "strftime") else str(ts)
                content = (it.get("content") or "").strip()
                channel = it.get("channel") or ""
                detail = f" · {channel}" if channel else ""
                snippet = (f"<div style='color:{MUT};font-size:11px;margin-top:2px'>"
                           f"{content[:120]}</div>") if content else ""
                items.append(
                    f"<div style='padding:6px 0;border-bottom:1px solid {BRD}'>"
                    f"<span style='color:{c}'>{ic} {lab}</span>"
                    f"<span style='color:{MUT};font-size:11px;margin-left:6px'>"
                    f"{ts_str}{detail}</span>{snippet}</div>"
                )
            history_html = "".join(items)

        return f"""
        <div style="font-family:-apple-system;color:{TXT}">
          <h2 style="margin:0;color:{H}">{r.get('name','')}</h2>
          <p style="color:{DIM};margin:2px 0 12px 0">
            {r.get('niche','')} · {r.get('city','')}/{r.get('state','')} · {r.get('company_size','') or '—'}
          </p>
          <p>
            {chip(f"Score {score}", bg=color, color=BG)}
            {chip(f"Match {match}%", bg=match_color, color=BG)}
            {chip(mode_label, bg=mode_color, color=BG)}
            {chip(prio_label, bg=prio_color, color=BG)}
            {chip(f"🔥 Hot {hot}", bg=hot_color, color="#FFFFFF")}
            {chip(st_label, bg=st_color, color="#FFFFFF")}
          </p>
          <p>{tags_html}</p>

          {msg_card}

          <h3 style="color:{H};margin-top:16px">Por que esse lead importa</h3>
          <p style="color:{TXT};white-space:pre-wrap">{r.get("why_matters") or "—"}</p>

          <h3 style="color:{H};margin-top:12px">Oportunidade</h3>
          <table>
            {li("Quando abordar", r.get("opportunity_when"))}
            {li("Melhor canal", r.get("opportunity_channel"))}
            {li("Oferta inicial", r.get("opportunity_offer"))}
            {li("Ticket estimado", r.get("ticket_estimate"))}
            {li("Receita anual estimada", r.get("revenue_year_estimate"))}
          </table>

          <h3 style="color:{H};margin-top:12px">Sinais detectados</h3>
          <p>{signals_html or "—"}</p>

          <h3 style="color:{H};margin-top:12px">Decisores</h3>
          <p style="color:{TXT}">{decisors_html}</p>

          <h3 style="color:{H};margin-top:12px">Stack / Tecnologias</h3>
          <p>{techs_html or "—"}</p>

          <h3 style="color:{H};margin-top:12px">Contato &amp; Empresa</h3>
          <table>
            {li("Telefone", r.get("phone"))}
            {li("WhatsApp", r.get("whatsapp"))}
            {li("Email", r.get("email"))}
            {li("Site", r.get("website"))}
            {li("Instagram", r.get("instagram"))}
            {li("LinkedIn", r.get("linkedin"))}
            {li("Endereço", r.get("address"))}
            {li("CNPJ", r.get("cnpj"))}
            {li("Funcionários", r.get("employees_estimate"))}
            {li("Anos de mercado", r.get("years_in_market"))}
            {li("Avaliação", f'{r.get("google_rating") or "—"} ({r.get("google_reviews") or 0} reviews)')}
            {li("Status CRM", r.get("status"))}
          </table>

          <h3 style="color:{H};margin-top:12px">Justificativa IA</h3>
          <p style="color:{TXT}">{r.get("score_reason") or "—"}</p>

          <h3 style="color:{H};margin-top:8px">Observações</h3>
          <p style="color:{TXT};white-space:pre-wrap">{r.get("observations") or "—"}</p>

          <h3 style="color:{H};margin-top:12px">Histórico de interações</h3>
          {history_html}
        </div>
        """

    def _export(self, fmt: str, only_selected: bool = False) -> None:
        rows = self._selected_rows()
        if not rows and not only_selected:
            rows = self.model._rows  # noqa: SLF001
        if not rows:
            QMessageBox.information(self, "Exportar",
                                    "Selecione leads ou tenha leads filtrados.")
            return
        try:
            if fmt == "csv":
                path = export_csv(rows)
            elif fmt == "xlsx":
                path = export_xlsx(rows)
            else:
                path = export_json(rows)
            QMessageBox.information(self, "Exportado",
                                    f"{len(rows)} leads exportados para:\n{path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(e))

    # ---------- contato direto ----------
    def _open_whatsapp(self) -> None:
        if not self._current_lead:
            return
        phone = best_contact_phone(self._current_lead)
        if not phone:
            QMessageBox.information(self, "Sem telefone", "Lead não tem telefone/WhatsApp.")
            return
        msg = (self._current_lead.get("message_a")
               or self._current_lead.get("pitch") or "")
        link = whatsapp_link(phone, msg)
        if link:
            QDesktopServices.openUrl(QUrl(link))
            try:
                LeadInteractionRepository.add(
                    int(self._current_lead["id"]), "whatsapp_sent",
                    content=msg[:400], channel=phone,
                )
            except Exception:
                pass

    def _open_email(self) -> None:
        if not self._current_lead:
            return
        email = self._current_lead.get("email") or ""
        if not email:
            return
        subj = f"Sobre {self._current_lead.get('name','')}"
        body = (self._current_lead.get("message_a")
                or self._current_lead.get("pitch") or "")
        link = mailto_link(email, subj, body)
        if link:
            QDesktopServices.openUrl(QUrl(link))
            try:
                LeadInteractionRepository.add(
                    int(self._current_lead["id"]), "email_sent",
                    content=body[:400], channel=email,
                )
            except Exception:
                pass

    def _copy_message(self, variant: str = "a") -> None:
        if not self._current_lead:
            return
        key = "message_a" if variant == "a" else "message_b"
        msg = (self._current_lead.get(key) or "").strip()
        if not msg:
            QMessageBox.information(self, "Sem mensagem",
                                    f"Versão {variant.upper()} não disponível.")
            return
        QGuiApplication.clipboard().setText(msg)
        QMessageBox.information(self, "Copiado",
                                f"Mensagem (versão {variant.upper()}) copiada.")

    def _mark_sent(self) -> None:
        if not self._current_lead:
            return
        lead_id = int(self._current_lead["id"])
        LeadRepository.update_send_status(lead_id, "enviado")
        try:
            LeadInteractionRepository.add(lead_id, "marked_sent",
                                          content="Marcado manualmente.")
        except Exception:
            pass
        # agenda próximo follow-up
        try:
            from app.config import get_settings
            days = get_settings().messages.followup_days
            if days:
                LeadRepository.schedule_next_followup(lead_id, days[0])
        except Exception:
            pass
        full = LeadRepository.get(lead_id) or self._current_lead
        self._current_lead = full
        self.detail_view.setHtml(self._render_detail(full))
        self.reload()
        self.leads_changed.emit()

    def _regen_ai_message(self) -> None:
        if not self._current_lead:
            return
        from app.services.messaging import regenerate_ai_messages
        lead_id = int(self._current_lead["id"])
        self.regen_btn.setEnabled(False)
        self.regen_btn.setText("⏳ Gerando…")
        QApplication.processEvents()
        try:
            msgs = regenerate_ai_messages(self._current_lead)
            LeadRepository.set_messages(
                lead_id,
                message_a=msgs["message_a"], message_b=msgs["message_b"],
                message_opener=msgs["message_opener"], message_tone=msgs["message_tone"],
                hot_score=msgs["hot_score"],
            )
            full = LeadRepository.get(lead_id) or self._current_lead
            self._current_lead = full
            self.detail_view.setHtml(self._render_detail(full))
            self.reload()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Falha IA", f"Não foi possível gerar: {e}")
        finally:
            self.regen_btn.setText("✨ Regerar IA")
            self.regen_btn.setEnabled(True)

    def _open_site(self) -> None:
        if not self._current_lead:
            return
        site = (self._current_lead.get("website") or "").strip()
        if not site:
            return
        if not site.startswith(("http://", "https://")):
            site = "https://" + site
        QDesktopServices.openUrl(QUrl(site))

    # ---------- bulk actions ----------
    def _refresh_campaigns(self) -> None:
        try:
            camps = CampaignRepository.list_all()
        except Exception:  # noqa: BLE001
            camps = []
        self.bulk_campaign.blockSignals(True)
        self.bulk_campaign.clear()
        self.bulk_campaign.addItem("Atribuir à campanha…", -1)
        self.bulk_campaign.addItem("[ Remover de campanha ]", 0)
        for c in camps:
            self.bulk_campaign.addItem(f"{c['name']} ({c['lead_count']})", c["id"])
        self.bulk_campaign.blockSignals(False)

    def _bulk_status(self, idx: int) -> None:
        if idx == 0:
            return
        status = self.bulk_status.itemData(idx)
        rows = self._selected_rows()
        if not rows or not status:
            self.bulk_status.setCurrentIndex(0); return
        ids = [int(r["id"]) for r in rows]
        n = LeadRepository.bulk_update_status(ids, status)
        self.bulk_status.setCurrentIndex(0)
        QMessageBox.information(self, "Status", f"{n} leads movidos para '{status}'.")
        self.reload(); self.leads_changed.emit()

    def _bulk_campaign(self, idx: int) -> None:
        cid = self.bulk_campaign.itemData(idx)
        if cid is None or cid == -1:
            return
        rows = self._selected_rows()
        if not rows:
            self.bulk_campaign.setCurrentIndex(0); return
        ids = [int(r["id"]) for r in rows]
        target = None if cid == 0 else int(cid)
        n = LeadRepository.bulk_assign_campaign(ids, target)
        self.bulk_campaign.setCurrentIndex(0)
        QMessageBox.information(self, "Campanha",
                                f"{n} leads {'removidos da campanha' if target is None else 'atribuídos'}.")
        self.reload(); self.leads_changed.emit()

    def _bulk_delete(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Excluir", "Selecione leads.")
            return
        if QMessageBox.question(self, "Excluir leads",
                                f"Excluir {len(rows)} leads? Essa ação é irreversível.",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        ids = [int(r["id"]) for r in rows]
        n = LeadRepository.delete_many(ids)
        QMessageBox.information(self, "Excluído", f"{n} leads removidos.")
        self.reload(); self.leads_changed.emit()

    def _wipe_all(self) -> None:
        total = self.model.rowCount()
        msg = (f"Apagar TODOS os leads ({total} visíveis), interações e histórico de buscas?\n\n"
               "Esta ação NÃO pode ser desfeita. Use quando os leads coletados forem ruins\n"
               "e você quiser começar do zero com filtros melhores.")
        if QMessageBox.question(
            self, "Limpar tudo", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        # confirma duas vezes
        confirm, ok = QInputDialog.getText(
            self, "Confirmação", 'Digite "LIMPAR" para confirmar:',
        )
        if not ok or confirm.strip().upper() != "LIMPAR":
            return
        n = LeadRepository.delete_all()
        self._current_lead = None
        self.detail_view.setHtml("")
        QMessageBox.information(self, "Limpo", f"{n} leads removidos.")
        self.reload(); self.leads_changed.emit()

    def _bulk_watch(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Monitorar", "Selecione leads.")
            return
        added = 0
        for r in rows:
            if r.get("website"):
                WatchRepository.add(name=r["name"], website=r["website"],
                                    lead_id=int(r["id"]))
                added += 1
        QMessageBox.information(self, "Monitorar",
                                f"{added} lead(s) adicionados ao monitoramento.")

    def _open_import(self) -> None:
        # navega para a página import via parent
        self.leads_changed.emit()
        win = self.window()
        if hasattr(win, "navigate_to"):
            win.navigate_to("import_leads")

    # ---------- column persistence ----------
    def _save_columns(self, *_) -> None:
        header = self.table.horizontalHeader()
        order = [header.visualIndex(i) for i in range(header.count())]
        self._settings.setValue("leads/column_order", order)

    def _restore_columns(self) -> None:
        order = self._settings.value("leads/column_order")
        if not order:
            return
        try:
            order = [int(x) for x in order]
        except Exception:  # noqa: BLE001
            return
        header = self.table.horizontalHeader()
        for logical, visual in enumerate(order):
            cur = header.visualIndex(logical)
            if cur != visual:
                header.moveSection(cur, visual)
