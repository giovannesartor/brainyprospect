"""Tela Dashboard."""
from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.database import LeadRepository, SearchRepository
from app.ui.widgets.cards import SectionTitle, StatCard


def _styled_chart(title: str) -> QChart:
    ch = QChart()
    ch.setTitle(title)
    ch.setBackgroundVisible(False)
    ch.setMargins(QChart().margins())
    ch.legend().setVisible(False)
    ch.setAnimationOptions(QChart.SeriesAnimations)
    return ch


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        # Cards
        cards_lay = QGridLayout()
        cards_lay.setSpacing(14)
        self.card_total = StatCard("Total de Leads", "0", "Base completa")
        self.card_today = StatCard("Leads Hoje", "0", "Capturados nas últimas 24h")
        self.card_score = StatCard("Score Médio IA", "0", "0 a 100")
        self.card_week = StatCard("Últimos 7 dias", "0", "Crescimento semanal")
        cards_lay.addWidget(self.card_total, 0, 0)
        cards_lay.addWidget(self.card_today, 0, 1)
        cards_lay.addWidget(self.card_score, 0, 2)
        cards_lay.addWidget(self.card_week, 0, 3)

        self.card_direct = StatCard("Venda Direta", "0", "Clientes finais encontrados")
        self.card_partners = StatCard("Parceiros", "0", "Multiplicadores comerciais")
        self.card_score_direct = StatCard("Score médio (Direta)", "0", "")
        self.card_score_partners = StatCard("Score médio (Parceiros)", "0", "")
        cards_lay.addWidget(self.card_direct, 1, 0)
        cards_lay.addWidget(self.card_partners, 1, 1)
        cards_lay.addWidget(self.card_score_direct, 1, 2)
        cards_lay.addWidget(self.card_score_partners, 1, 3)

        self.card_max = StatCard("🔥 Prioridade Máxima", "0", "Atacar agora")
        self.card_high = StatCard("⚡ Alta Conversão", "0", "Alvos quentes")
        self.card_pipeline = StatCard("Em pipeline", "0", "Qualificados → Proposta")
        self.card_won = StatCard("Fechados", "0", "Conversão acumulada")
        cards_lay.addWidget(self.card_max, 2, 0)
        cards_lay.addWidget(self.card_high, 2, 1)
        cards_lay.addWidget(self.card_pipeline, 2, 2)
        cards_lay.addWidget(self.card_won, 2, 3)
        root.addLayout(cards_lay)

        # Linha de gráficos
        charts_row = QHBoxLayout(); charts_row.setSpacing(14)

        funnel_box = QFrame(); funnel_box.setObjectName("card")
        fl = QVBoxLayout(funnel_box); fl.setContentsMargins(14, 12, 14, 12)
        fl.addWidget(SectionTitle("Funil de Pipeline"))
        self.funnel_chart = _styled_chart("")
        self.funnel_view = QChartView(self.funnel_chart)
        self.funnel_view.setRenderHint(QPainter.Antialiasing)
        self.funnel_view.setMinimumHeight(220)
        fl.addWidget(self.funnel_view)
        charts_row.addWidget(funnel_box, 1)

        days_box = QFrame(); days_box.setObjectName("card")
        dl = QVBoxLayout(days_box); dl.setContentsMargins(14, 12, 14, 12)
        dl.addWidget(SectionTitle("Leads / dia (últimos 14)"))
        self.days_chart = _styled_chart("")
        self.days_view = QChartView(self.days_chart)
        self.days_view.setRenderHint(QPainter.Antialiasing)
        self.days_view.setMinimumHeight(220)
        dl.addWidget(self.days_view)
        charts_row.addWidget(days_box, 1)

        cities_box = QFrame(); cities_box.setObjectName("card")
        cl = QVBoxLayout(cities_box); cl.setContentsMargins(14, 12, 14, 12)
        cl.addWidget(SectionTitle("Top Cidades"))
        self.cities_chart = _styled_chart("")
        self.cities_view = QChartView(self.cities_chart)
        self.cities_view.setRenderHint(QPainter.Antialiasing)
        self.cities_view.setMinimumHeight(220)
        cl.addWidget(self.cities_view)
        charts_row.addWidget(cities_box, 1)

        root.addLayout(charts_row)

        # Linha de listas
        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        # Top nichos
        niches_box = QFrame()
        niches_box.setObjectName("card")
        nl = QVBoxLayout(niches_box)
        nl.setContentsMargins(18, 14, 18, 14)
        nl.addWidget(SectionTitle("Nichos mais encontrados"))
        self.niches_list = QListWidget()
        self.niches_list.setStyleSheet("border:none; background:transparent;")
        nl.addWidget(self.niches_list, 1)
        bottom.addWidget(niches_box, 1)

        # Últimas pesquisas
        searches_box = QFrame()
        searches_box.setObjectName("card")
        sl = QVBoxLayout(searches_box)
        sl.setContentsMargins(18, 14, 18, 14)
        sl.addWidget(SectionTitle("Últimas pesquisas"))
        self.searches_list = QListWidget()
        self.searches_list.setStyleSheet("border:none; background:transparent;")
        sl.addWidget(self.searches_list, 1)
        bottom.addWidget(searches_box, 1)

        root.addLayout(bottom, 1)

        # Refresh
        actions = QHBoxLayout()
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.setObjectName("ghost")
        self.refresh_btn.clicked.connect(self.reload)
        actions.addStretch()
        actions.addWidget(self.refresh_btn)
        root.addLayout(actions)

        self.reload()

    def reload(self) -> None:
        stats = LeadRepository.stats()
        self.card_total.set_value(f"{stats['total']:,}".replace(",", "."))
        self.card_today.set_value(str(stats["today"]))
        self.card_score.set_value(f"{stats['avg_score']}")
        self.card_week.set_value(str(stats["weekly"]))
        self.card_direct.set_value(str(stats["direct_total"]))
        self.card_partners.set_value(str(stats["partners_total"]))
        self.card_score_direct.set_value(f"{stats['avg_score_direct']}")
        self.card_score_partners.set_value(f"{stats['avg_score_partners']}")

        prio = LeadRepository.priority_distribution()
        pipe = LeadRepository.pipeline_stats()
        self.card_max.set_value(str(prio.get("maxima", 0)))
        self.card_high.set_value(str(prio.get("alta", 0)))
        self.card_pipeline.set_value(
            str(pipe.get("qualificado", 0) + pipe.get("contatado", 0)
                + pipe.get("respondeu", 0) + pipe.get("reuniao", 0)
                + pipe.get("proposta", 0))
        )
        self.card_won.set_value(str(pipe.get("fechado", 0)))

        self.niches_list.clear()
        max_count = max((c for _, c in stats["top_niches"]), default=1)
        for niche, count in stats["top_niches"]:
            ratio = int((count / max_count) * 100)
            bar = "▮" * max(1, ratio // 8)
            item = QListWidgetItem(f"  {niche:<28}  {count:>4}   {bar}")
            self.niches_list.addItem(item)
        if self.niches_list.count() == 0:
            self.niches_list.addItem("Nenhum lead ainda. Faça sua primeira busca.")

        self.searches_list.clear()
        for s in SearchRepository.list_recent(15):
            ts = s["created_at"].strftime("%d/%m %H:%M")
            line = f"  [{ts}]  {s['niche'] or s['input']}  ({s['city']}) — {s['total']} leads"
            self.searches_list.addItem(line)
        if self.searches_list.count() == 0:
            self.searches_list.addItem("Nenhuma busca registrada.")

        self._reload_charts(pipe)

    def _reload_charts(self, pipe: dict[str, int]) -> None:
        # Funil pipeline
        self.funnel_chart.removeAllSeries()
        for ax in list(self.funnel_chart.axes()):
            self.funnel_chart.removeAxis(ax)
        order = [("novo", "Novo"), ("qualificado", "Qual."), ("contatado", "Contatado"),
                 ("respondeu", "Resp."), ("reuniao", "Reunião"),
                 ("proposta", "Proposta"), ("fechado", "Fechado")]
        bars = QBarSet("Pipeline")
        cats = []
        for k, label in order:
            bars.append(pipe.get(k, 0))
            cats.append(label)
        series = QBarSeries(); series.append(bars)
        self.funnel_chart.addSeries(series)
        ax_x = QBarCategoryAxis(); ax_x.append(cats)
        ax_y = QValueAxis(); ax_y.setLabelFormat("%d")
        self.funnel_chart.addAxis(ax_x, Qt.AlignBottom); series.attachAxis(ax_x)
        self.funnel_chart.addAxis(ax_y, Qt.AlignLeft); series.attachAxis(ax_y)

        # Leads/dia
        self.days_chart.removeAllSeries()
        for ax in list(self.days_chart.axes()):
            self.days_chart.removeAxis(ax)
        days = LeadRepository.leads_per_day(14)
        line = QLineSeries()
        for i, (_, n) in enumerate(days):
            line.append(i, n)
        self.days_chart.addSeries(line)
        dax_x = QBarCategoryAxis(); dax_x.append([d for d, _ in days])
        dax_y = QValueAxis(); dax_y.setLabelFormat("%d")
        self.days_chart.addAxis(dax_x, Qt.AlignBottom); line.attachAxis(dax_x)
        self.days_chart.addAxis(dax_y, Qt.AlignLeft); line.attachAxis(dax_y)

        # Top cidades
        self.cities_chart.removeAllSeries()
        for ax in list(self.cities_chart.axes()):
            self.cities_chart.removeAxis(ax)
        cities = LeadRepository.top_cities(8)
        cset = QBarSet("Cidades")
        cnames = []
        for c, n in cities:
            cset.append(n); cnames.append((c[:14] or "—"))
        cseries = QBarSeries(); cseries.append(cset)
        self.cities_chart.addSeries(cseries)
        cax_x = QBarCategoryAxis(); cax_x.append(cnames)
        cax_y = QValueAxis(); cax_y.setLabelFormat("%d")
        self.cities_chart.addAxis(cax_x, Qt.AlignBottom); cseries.attachAxis(cax_x)
        self.cities_chart.addAxis(cax_y, Qt.AlignLeft); cseries.attachAxis(cax_y)
