"""Importador de leads CSV/XLSX com mapeamento de colunas."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadRepository

# Campos que podem ser mapeados (chave_db, label_amigável, exemplos)
TARGET_FIELDS = [
    ("name", "Nome / Empresa"),
    ("niche", "Nicho / Segmento"),
    ("city", "Cidade"),
    ("state", "UF"),
    ("country", "País"),
    ("address", "Endereço"),
    ("website", "Site"),
    ("phone", "Telefone"),
    ("whatsapp", "WhatsApp"),
    ("email", "Email"),
    ("instagram", "Instagram"),
    ("linkedin", "LinkedIn"),
    ("score", "Score"),
    ("status", "Status"),
    ("tags", "Tags"),
    ("cnpj", "CNPJ"),
    ("observations", "Observações"),
    ("pitch", "Pitch"),
]


def _auto_match(col: str) -> str:
    """Tenta inferir qual campo do banco corresponde à coluna."""
    c = col.lower().strip()
    aliases = {
        "name": ["nome", "empresa", "razao social", "razão social", "company", "name"],
        "niche": ["nicho", "segmento", "categoria", "industry", "ramo"],
        "city": ["cidade", "city", "municipio", "município"],
        "state": ["uf", "estado", "state"],
        "country": ["país", "pais", "country"],
        "address": ["endereco", "endereço", "address"],
        "website": ["site", "website", "url", "homepage"],
        "phone": ["telefone", "phone", "fone", "tel"],
        "whatsapp": ["whatsapp", "whats", "wa"],
        "email": ["email", "e-mail", "mail"],
        "instagram": ["instagram", "ig", "insta"],
        "linkedin": ["linkedin", "linked-in"],
        "score": ["score", "pontuacao", "pontuação"],
        "status": ["status", "etapa"],
        "tags": ["tags", "etiquetas"],
        "cnpj": ["cnpj"],
        "observations": ["obs", "observacao", "observação", "notes", "notas"],
        "pitch": ["pitch", "abordagem"],
    }
    for k, words in aliases.items():
        for w in words:
            if w == c or w in c:
                return k
    return ""


class ImportPage(QWidget):
    """Importação de planilhas com mapeamento visual de colunas."""
    leads_updated = Signal()

    def __init__(self) -> None:
        super().__init__()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        page = QWidget(); scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 24); root.setSpacing(16)

        intro = QLabel(
            "📥  <b>Importar Leads</b> — Carregue uma planilha CSV ou XLSX. "
            "Você poderá mapear as colunas do arquivo para os campos do Brainy."
        )
        intro.setObjectName("intro"); intro.setWordWrap(True)
        root.addWidget(intro)

        # Card de upload
        up_card = QFrame(); up_card.setObjectName("sectionCard")
        ul = QVBoxLayout(up_card); ul.setContentsMargins(20, 16, 20, 16); ul.setSpacing(10)
        head = QLabel("1. Selecione o arquivo"); head.setObjectName("sectionHead")
        ul.addWidget(head)
        row = QHBoxLayout()
        self.file_lbl = QLabel("Nenhum arquivo selecionado")
        self.file_lbl.setObjectName("muted")
        choose_btn = QPushButton("📂  Escolher arquivo CSV/XLSX")
        choose_btn.setObjectName("primary")
        choose_btn.clicked.connect(self._pick_file)
        row.addWidget(self.file_lbl, 1); row.addWidget(choose_btn)
        ul.addLayout(row)
        root.addWidget(up_card)

        # Card de preview + mapeamento
        self.map_card = QFrame(); self.map_card.setObjectName("sectionCard")
        ml = QVBoxLayout(self.map_card)
        ml.setContentsMargins(20, 16, 20, 16); ml.setSpacing(10)
        head2 = QLabel("2. Mapeie as colunas"); head2.setObjectName("sectionHead")
        ml.addWidget(head2)
        ml.addWidget(QLabel("Para cada coluna do arquivo, escolha o campo equivalente "
                            "no Brainy. Deixe vazio para ignorar."))
        self.map_widget = QWidget()
        self.map_layout = QVBoxLayout(self.map_widget)
        self.map_layout.setContentsMargins(0, 0, 0, 0); self.map_layout.setSpacing(6)
        ml.addWidget(self.map_widget)

        ml.addWidget(QLabel("Pré-visualização (5 primeiras linhas):"))
        self.preview = QTableWidget(0, 0)
        self.preview.setMinimumHeight(160)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        ml.addWidget(self.preview)
        self.map_card.setVisible(False)
        root.addWidget(self.map_card)

        # Ação
        self.action_card = QFrame(); self.action_card.setObjectName("sectionCard")
        al = QVBoxLayout(self.action_card)
        al.setContentsMargins(20, 16, 20, 16); al.setSpacing(8)
        head3 = QLabel("3. Importar"); head3.setObjectName("sectionHead")
        al.addWidget(head3)
        self.summary_lbl = QLabel(""); self.summary_lbl.setObjectName("muted")
        al.addWidget(self.summary_lbl)
        action_row = QHBoxLayout(); action_row.addStretch()
        self.import_btn = QPushButton("📥  Importar todos")
        self.import_btn.setObjectName("primary")
        self.import_btn.setMinimumWidth(180); self.import_btn.setMinimumHeight(40)
        self.import_btn.clicked.connect(self._do_import)
        action_row.addWidget(self.import_btn)
        al.addLayout(action_row)
        self.action_card.setVisible(False)
        root.addWidget(self.action_card)

        root.addStretch()

        self._df: pd.DataFrame | None = None
        self._combos: dict[str, QComboBox] = {}

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar planilha", "",
            "Planilhas (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            p = Path(path)
            if p.suffix.lower() == ".csv":
                df = pd.read_csv(p)
            else:
                df = pd.read_excel(p)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro", f"Falha ao ler arquivo:\n{e}")
            return
        self._df = df.fillna("")
        self.file_lbl.setText(f"📄 {p.name}  ·  {len(df)} linhas  ·  {len(df.columns)} colunas")
        self._build_map()
        self._fill_preview()
        self.map_card.setVisible(True)
        self.action_card.setVisible(True)
        self.summary_lbl.setText(f"{len(df)} linhas prontas para importar.")

    def _build_map(self) -> None:
        # limpa
        while self.map_layout.count():
            item = self.map_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._combos.clear()
        if self._df is None:
            return
        for col in self._df.columns:
            row = QHBoxLayout()
            lbl = QLabel(str(col))
            lbl.setMinimumWidth(220)
            lbl.setStyleSheet("font-weight:600")
            cb = QComboBox()
            cb.addItem("— ignorar —", "")
            for k, label in TARGET_FIELDS:
                cb.addItem(label, k)
            # auto-match
            guess = _auto_match(str(col))
            if guess:
                idx = cb.findData(guess)
                if idx > 0:
                    cb.setCurrentIndex(idx)
            self._combos[str(col)] = cb
            row.addWidget(lbl); row.addWidget(cb, 1)
            container = QWidget(); container.setLayout(row)
            self.map_layout.addWidget(container)

    def _fill_preview(self) -> None:
        if self._df is None:
            return
        df = self._df.head(5)
        self.preview.setColumnCount(len(df.columns))
        self.preview.setRowCount(len(df))
        self.preview.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r, (_, row) in enumerate(df.iterrows()):
            for c, val in enumerate(row.values):
                self.preview.setItem(r, c, QTableWidgetItem(str(val)))
        self.preview.resizeColumnsToContents()

    def _do_import(self) -> None:
        if self._df is None:
            return
        # monta lista de dicts mapeados
        leads: list[dict] = []
        for _, row in self._df.iterrows():
            data: dict = {"prospection_mode": "direct_sale", "tags": "Importado"}
            for col, cb in self._combos.items():
                target = cb.currentData()
                if not target:
                    continue
                v = row.get(col, "")
                if pd.isna(v):
                    continue
                # int safe
                if target == "score":
                    try:
                        data[target] = int(float(v))
                    except Exception:  # noqa: BLE001
                        continue
                else:
                    data[target] = str(v).strip()
            if data.get("name"):
                leads.append(data)
        if not leads:
            QMessageBox.warning(self, "Atenção",
                                "Nenhuma linha válida — você precisa mapear ao menos a coluna 'Nome'.")
            return
        try:
            inserted = LeadRepository.upsert_many(leads)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro", str(e))
            return
        QMessageBox.information(
            self, "Importado",
            f"✔ {inserted} novos leads importados (de {len(leads)} válidos).\n"
            "Veja em Leads → Todos os Leads."
        )
        self.leads_updated.emit()
