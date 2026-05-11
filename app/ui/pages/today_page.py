"""Página 'Hoje você deve abordar' — top leads quentes a contatar agora."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadInteractionRepository, LeadRepository
from app.services.followup_scheduler import compute_due_followups
from app.ui.theme import colors as theme_colors, on_theme_changed
from app.ui.widgets.cards import SectionTitle
from app.utils.contact import best_contact_phone, mailto_link, whatsapp_link


class TodayPage(QWidget):
    """Top 10 leads para abordar hoje + follow-ups vencidos."""

    leads_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.addWidget(SectionTitle("Hoje você deve abordar"))
        head.addStretch()
        self.refresh_btn = QPushButton("↻ Atualizar")
        self.refresh_btn.setObjectName("ghost")
        self.refresh_btn.clicked.connect(self.reload)
        head.addWidget(self.refresh_btn)
        root.addLayout(head)

        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color:{theme_colors()['text_dim']};font-size:13px")
        root.addWidget(self.summary)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        self.container = QWidget()
        self.container_lay = QVBoxLayout(self.container)
        self.container_lay.setContentsMargins(0, 0, 0, 0)
        self.container_lay.setSpacing(10)
        self.container_lay.addStretch()
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)

        try:
            on_theme_changed(lambda _t: self.reload())
        except Exception:
            pass

        self.reload()

    def reload(self) -> None:
        c = theme_colors()
        # atualiza cor do resumo conforme tema
        self.summary.setStyleSheet(f"color:{c['text_dim']};font-size:13px")
        # limpa
        while self.container_lay.count() > 1:
            it = self.container_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        hot = LeadRepository.today_list(limit=10)
        try:
            due = compute_due_followups()
        except Exception:
            due = []

        self.summary.setText(
            f"🔥 {len(hot)} leads quentes para 1ª abordagem  "
            f"·  ⏰ {len(due)} follow-ups vencidos"
        )

        if not hot and not due:
            empty = QLabel(
                "Nenhum lead pendente. Rode uma prospecção em <b>Prospectar</b>."
            )
            empty.setStyleSheet(
                f"color:{c['text_dim']};padding:24px;text-align:center"
            )
            self.container_lay.insertWidget(0, empty)
            return

        if due:
            label = QLabel(f"⏰  Follow-ups vencidos ({len(due)})")
            label.setObjectName("warnHeader")
            self.container_lay.insertWidget(self.container_lay.count() - 1, label)
            for lead in due[:10]:
                self.container_lay.insertWidget(
                    self.container_lay.count() - 1,
                    self._build_card(lead, kind="followup"),
                )

        if hot:
            label = QLabel(f"🔥  Quentes — abordar primeiro")
            label.setObjectName("dangerHeader")
            self.container_lay.insertWidget(self.container_lay.count() - 1, label)
            for lead in hot:
                self.container_lay.insertWidget(
                    self.container_lay.count() - 1,
                    self._build_card(lead, kind="hot"),
                )

    def _build_card(self, lead: dict, kind: str) -> QFrame:
        c = theme_colors()
        TXT = c["text"]; DIM = c["text_dim"]; SOFT = c["text_mute"]
        ACCENT = c["accent_hi"]
        card = QFrame(); card.setObjectName("card")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel(
            f"<b style='color:{TXT};font-size:14px'>{lead.get('name','')}</b> "
            f"<span style='color:{DIM}'>· {lead.get('niche','')} · "
            f"{lead.get('city','')}/{lead.get('state','')}</span>"
        )
        title.setTextFormat(Qt.RichText)
        top.addWidget(title); top.addStretch()

        hot_score = int(lead.get("hot_score") or 0)
        chip_color = "#EF4444" if hot_score >= 70 else ("#F59E0B" if hot_score >= 40 else "#6B7280")
        badge = QLabel(f"🔥 {hot_score}")
        badge.setStyleSheet(
            f"background:{chip_color};color:white;padding:3px 10px;"
            f"border-radius:10px;font-weight:700;font-size:11px"
        )
        top.addWidget(badge)
        lay.addLayout(top)

        info = []
        if lead.get("phone"): info.append(f"📞 {lead['phone']}")
        if lead.get("whatsapp"): info.append(f"💬 {lead['whatsapp']}")
        if lead.get("email"): info.append(f"✉ {lead['email']}")
        if info:
            il = QLabel("  ·  ".join(info))
            il.setStyleSheet(f"color:{SOFT};font-size:12px")
            lay.addWidget(il)

        # mensagem (opener visível)
        opener = (lead.get("message_opener") or "").strip()
        if opener:
            op = QLabel(f"<i style='color:{ACCENT}'>“{opener}”</i>")
            op.setTextFormat(Qt.RichText); op.setWordWrap(True)
            op.setStyleSheet("padding:4px 0")
            lay.addWidget(op)

        actions = QHBoxLayout()
        actions.addStretch()

        wa_btn = QPushButton("💬 WhatsApp")
        wa_btn.setObjectName("primary")
        wa_btn.setEnabled(bool(best_contact_phone(lead)))
        wa_btn.clicked.connect(lambda _=False, l=lead: self._send_wa(l))
        actions.addWidget(wa_btn)

        em_btn = QPushButton("✉ Email")
        em_btn.setEnabled(bool(lead.get("email")))
        em_btn.clicked.connect(lambda _=False, l=lead: self._send_email(l))
        actions.addWidget(em_btn)

        copy_btn = QPushButton("📋 Copiar")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(lambda _=False, l=lead: self._copy(l))
        actions.addWidget(copy_btn)

        if kind == "hot":
            mark_btn = QPushButton("✓ Enviado")
            mark_btn.setObjectName("ghost")
            mark_btn.clicked.connect(lambda _=False, l=lead: self._mark_sent(l))
            actions.addWidget(mark_btn)

        lay.addLayout(actions)
        return card

    # ------------------------- ações -------------------------
    def _msg(self, lead: dict) -> str:
        return (lead.get("message_a") or lead.get("pitch") or "").strip()

    def _send_wa(self, lead: dict) -> None:
        phone = best_contact_phone(lead)
        if not phone:
            return
        link = whatsapp_link(phone, self._msg(lead))
        if link:
            QDesktopServices.openUrl(QUrl(link))
            try:
                LeadInteractionRepository.add(
                    int(lead["id"]), "whatsapp_sent",
                    content=self._msg(lead)[:400], channel=phone,
                )
            except Exception:
                pass
            # marca como enviado para sair da fila de "Hoje"
            self._mark_sent(lead)

    def _send_email(self, lead: dict) -> None:
        email = lead.get("email") or ""
        if not email:
            return
        link = mailto_link(email, f"Sobre {lead.get('name','')}", self._msg(lead))
        if link:
            QDesktopServices.openUrl(QUrl(link))
            try:
                LeadInteractionRepository.add(
                    int(lead["id"]), "email_sent",
                    content=self._msg(lead)[:400], channel=email,
                )
            except Exception:
                pass
            self._mark_sent(lead)

    def _copy(self, lead: dict) -> None:
        msg = self._msg(lead)
        if not msg:
            QMessageBox.information(self, "Sem mensagem", "Lead sem mensagem gerada.")
            return
        QGuiApplication.clipboard().setText(msg)
        QMessageBox.information(self, "Copiado", "Mensagem copiada.")

    def _mark_sent(self, lead: dict) -> None:
        LeadRepository.update_send_status(int(lead["id"]), "enviado")
        try:
            LeadInteractionRepository.add(
                int(lead["id"]), "marked_sent", content="Marcado em 'Hoje'.",
            )
            from app.config import get_settings
            days = get_settings().messages.followup_days
            if days:
                LeadRepository.schedule_next_followup(int(lead["id"]), days[0])
        except Exception:
            pass
        self.reload()
        self.leads_changed.emit()
