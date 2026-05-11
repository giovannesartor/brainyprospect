// ============================================================================
// Brainy Prospect — Web App (Alpine component)
// Features: tema, jobs em background, mobile drawer, charts, kanban, lookalike,
// objections, brainy chat, today, monitoring, tour guiado, push notifications.
// ============================================================================

window.__USER__ = (function () {
  try { return JSON.parse(document.getElementById('__user_data__')?.textContent || '{}'); }
  catch { return {}; }
})();

const HUNT_JOB_KEY = 'bp_hunt_job_id';
const TOUR_KEY = 'bp_tour_done_v2';
const PUSH_KEY = 'bp_push_optin';
const saveHuntJobId = (id) => { try { id ? localStorage.setItem(HUNT_JOB_KEY, id) : localStorage.removeItem(HUNT_JOB_KEY); } catch {} };
const loadHuntJobId = () => { try { return localStorage.getItem(HUNT_JOB_KEY); } catch { return null; } };

function appShell() {
  return {
    user: window.__USER__ || {},
    tab: (location.hash || '').replace('#','') || localStorage.getItem('bp_tab') || 'today',
    sidebarOpen: false,
    theme: localStorage.getItem('bp_theme') || 'dark',

    menu: [
      { id: 'today',      label: 'Hoje',          icon: 'fire' },
      { id: 'dashboard',  label: 'Dashboard',     icon: 'chart' },
      { id: 'hunt',       label: 'Prospectar',    icon: 'rocket' },
      { id: 'leads',      label: 'Leads',         icon: 'users' },
      { id: 'pipeline',   label: 'Pipeline',      icon: 'compass' },
      { id: 'lookalike',  label: 'Lookalike',     icon: 'mirror' },
      { id: 'objections', label: 'Objeções IA',   icon: 'shield' },
      { id: 'chat',       label: 'Brainy Chat',   icon: 'chat' },
      { id: 'campaigns',  label: 'Campanhas',     icon: 'target' },
      { id: 'history',    label: 'Histórico',     icon: 'clock' },
      { id: 'jobs',       label: 'Jobs',          icon: 'cog' },
    ],

    titles: {
      today:      ['Hoje',           'Leads quentes e pendências do dia'],
      dashboard:  ['Dashboard',      'KPIs, gráficos e tendências'],
      hunt:       ['Prospectar',     'Site/descrição → leads qualificados'],
      leads:      ['Leads',          'Base completa com filtros'],
      pipeline:   ['Pipeline',       'Kanban de vendas (arraste entre colunas)'],
      lookalike:  ['Lookalike',      'Encontre empresas parecidas com seus melhores clientes'],
      objections: ['Objeções IA',    'Respostas prontas para objeções comuns'],
      chat:       ['Brainy Chat',    'Pergunte qualquer coisa sobre seus leads'],
      campaigns:  ['Campanhas',      'Agrupe leads por estratégia'],
      history:    ['Histórico',      'Buscas executadas'],
      jobs:       ['Jobs',           'Tarefas em background'],
    },
    currentTitle()    { return (this.titles[this.tab] || ['', ''])[0]; },
    currentSubtitle() { return (this.titles[this.tab] || ['', ''])[1]; },

    // ---------- estado das abas ----------
    dash: {},
    chartsData: null,
    today: { hot_leads: [], in_contact: [], responded: [], closing: [], summary: {} },
    leads: [],
    leadsFilters: { text: '', city: '', niche: '', status: '', priority: '' },
    campaigns: [],
    newCampaign: { name: '', description: '', target_mode: 'direct_sale', color: '#6366F1' },
    searches: [],
    jobs: [],

    pipelineCols: ['novo','qualificado','contatado','respondeu','reuniao','proposta','fechado','perdido'],
    pipelineLeads: {},

    hunt: {
      source_input: '', is_website: false,
      manual_niches: [], city: '', state: '', country: 'Brasil',
      max_per_niche: 15, use_ai_qualification: true, mode: 'direct_sale',
    },
    huntNiches: '',
    huntJob: null,
    pollHandle: null,
    analysis: null,
    analyzing: false,
    submittingHunt: false,

    lookalike: { lead_id: null, source_input: '', is_website: true, max_per_niche: 15, city: '', state: '', mode: 'direct_sale' },
    lookalikeJob: null,

    objection: { text: '', context: '', lead_id: null },
    objectionResult: null,
    objectionLoading: false,

    chat: { input: '', history: [], loading: false },

    leadOpen: false,
    currentLead: null,

    pushOptIn: false,

    // ====================================================
    // BOOT
    // ====================================================
    async boot() {
      this.applyTheme(this.theme);
      this.pushOptIn = localStorage.getItem(PUSH_KEY) === '1';

      await this.refreshAll();
      await this.loadCharts();

      // Restaura job em andamento
      const savedJobId = loadHuntJobId();
      if (savedJobId) await this.resumeJob(savedJobId);

      setInterval(() => {
        if (this.tab === 'dashboard') { this.loadDashboard(); this.loadCharts(); }
        if (this.tab === 'today') this.loadToday();
      }, 30000);

      this.$watch('tab', v => {
        try { localStorage.setItem('bp_tab', v); location.hash = v; } catch {}
        this.sidebarOpen = false;
        if (v === 'pipeline') this.loadPipeline();
        if (v === 'today')    this.loadToday();
        if (v === 'dashboard') this.loadCharts();
      });
      this.$watch('theme', v => this.applyTheme(v));

      // Tour guiado (primeira vez)
      if (!localStorage.getItem(TOUR_KEY)) {
        setTimeout(() => this.startTour(), 800);
      }

      // Carrega today inicial se for a aba ativa
      if (this.tab === 'today') this.loadToday();
      if (this.tab === 'pipeline') this.loadPipeline();
    },

    setTab(id) { this.tab = id; this.sidebarOpen = false; },

    // ====================================================
    // THEME
    // ====================================================
    applyTheme(v) { try { localStorage.setItem('bp_theme', v); } catch {} document.documentElement.dataset.theme = v; },
    toggleTheme() { this.theme = (this.theme === 'dark') ? 'light' : 'dark'; },

    // ====================================================
    // API helper
    // ====================================================
    async api(path, opts = {}) {
      const res = await fetch(path, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
        ...opts,
      });
      if (res.status === 401) { window.location.href = '/login'; throw new Error('401'); }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || ('HTTP ' + res.status));
      }
      return res.json();
    },

    // ====================================================
    // LOADERS
    // ====================================================
    async refreshAll() {
      await Promise.all([
        this.loadDashboard(), this.loadLeads(), this.loadCampaigns(),
        this.loadSearches(), this.loadJobs(), this.loadToday(),
      ]);
    },
    async loadDashboard() { try { this.dash = await this.api('/api/dashboard'); } catch (e) { console.warn(e); } },
    async loadCharts()    {
      try {
        this.chartsData = await this.api('/api/charts');
        this.$nextTick(() => this.renderCharts());
      } catch (e) { console.warn(e); }
    },
    async loadToday()     { try { this.today = await this.api('/api/today'); } catch (e) { console.warn(e); } },
    async loadLeads()     {
      const q = new URLSearchParams();
      Object.entries(this.leadsFilters).forEach(([k, v]) => { if (v) q.set(k, v); });
      q.set('limit', 200);
      try { const r = await this.api('/api/leads?' + q.toString()); this.leads = r.items || []; } catch (e) { console.warn(e); }
    },
    async loadCampaigns() { try { this.campaigns = await this.api('/api/campaigns'); } catch (e) { console.warn(e); } },
    async loadSearches()  { try { this.searches  = await this.api('/api/searches?limit=50'); } catch (e) { console.warn(e); } },
    async loadJobs()      { try { this.jobs      = await this.api('/api/jobs'); } catch (e) { console.warn(e); } },

    async loadPipeline() {
      try {
        const all = await this.api('/api/leads?limit=2000');
        const items = all.items || [];
        const grouped = {};
        for (const c of this.pipelineCols) grouped[c] = [];
        for (const l of items) {
          const s = (l.status || 'novo');
          if (!grouped[s]) grouped[s] = [];
          grouped[s].push(l);
        }
        this.pipelineLeads = grouped;
        this.$nextTick(() => this.initSortable());
      } catch (e) { window.bpToast?.(e.message, 'error'); }
    },

    initSortable() {
      if (!window.Sortable) return;
      for (const c of this.pipelineCols) {
        const el = document.getElementById('kanban-col-' + c);
        if (!el || el._sortable) continue;
        el._sortable = new Sortable(el, {
          group: 'pipeline',
          animation: 160,
          ghostClass: 'opacity-50',
          dragClass: 'rotate-2',
          onEnd: async (evt) => {
            const id = parseInt(evt.item.dataset.id, 10);
            const newStatus = evt.to.dataset.col;
            if (!id || !newStatus) return;
            try {
              await this.api('/api/leads/' + id, { method: 'PATCH', body: JSON.stringify({ status: newStatus }) });
              window.bpToast?.(`Lead movido para "${newStatus}"`, 'success', 2200);
            } catch (e) { window.bpToast?.(e.message, 'error'); this.loadPipeline(); }
          },
        });
      }
    },

    // ====================================================
    // CHARTS
    // ====================================================
    _charts: {},
    renderCharts() {
      if (!window.Chart || !this.chartsData) return;
      const isDark = this.theme === 'dark';
      const grid = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)';
      const tick = isDark ? '#9ca3af' : '#475569';
      Chart.defaults.color = tick;
      Chart.defaults.borderColor = grid;

      // Leads por dia
      this._mountChart('chartPerDay', {
        type: 'line',
        data: {
          labels: this.chartsData.per_day.map(d => d.date),
          datasets: [{
            label: 'Leads/dia',
            data: this.chartsData.per_day.map(d => d.count),
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99,102,241,0.18)',
            fill: true, tension: 0.35, borderWidth: 2, pointRadius: 3,
          }],
        },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { grid: { color: grid } }, y: { grid: { color: grid }, beginAtZero: true } } },
      });

      // Pipeline (donut)
      const pipe = this.chartsData.pipeline || {};
      this._mountChart('chartPipeline', {
        type: 'doughnut',
        data: {
          labels: Object.keys(pipe),
          datasets: [{
            data: Object.values(pipe),
            backgroundColor: ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444','#22c55e','#64748b'],
            borderWidth: 0,
          }],
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '65%',
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } } },
      });

      // Conversão por nicho
      const niches = this.chartsData.niche_conversion || [];
      this._mountChart('chartNiches', {
        type: 'bar',
        data: {
          labels: niches.map(n => n.niche),
          datasets: [
            { label: 'Total',     data: niches.map(n => n.total),     backgroundColor: '#6366f1' },
            { label: 'Contatado', data: niches.map(n => n.contacted), backgroundColor: '#8b5cf6' },
            { label: 'Fechado',   data: niches.map(n => n.won),       backgroundColor: '#10b981' },
          ],
        },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y',
          plugins: { legend: { position: 'bottom' } },
          scales: { x: { stacked: false, grid: { color: grid } }, y: { grid: { color: grid } } } },
      });

      // Cidades top
      const cities = this.chartsData.cities || [];
      this._mountChart('chartCities', {
        type: 'bar',
        data: {
          labels: cities.map(c => c.city),
          datasets: [{ label: 'Leads', data: cities.map(c => c.count), backgroundColor: '#06b6d4' }],
        },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { grid: { color: grid } }, y: { grid: { color: grid }, beginAtZero: true } } },
      });
    },
    _mountChart(id, cfg) {
      const el = document.getElementById(id);
      if (!el) return;
      if (this._charts[id]) { this._charts[id].destroy(); }
      this._charts[id] = new Chart(el.getContext('2d'), cfg);
    },

    // ====================================================
    // KPIs
    // ====================================================
    kpis() {
      const s = this.dash.stats || {};
      return [
        { label: 'Total leads',  value: s.total ?? 0,    hint: (s.today ?? 0) + ' hoje' },
        { label: 'Score médio',  value: s.avg_score ?? 0, hint: 'média global' },
        { label: 'Esta semana',  value: s.weekly ?? 0,    hint: 'últimos 7 dias' },
        { label: 'Direto/Parc.', value: (s.direct_total ?? 0) + ' / ' + (s.partners_total ?? 0), hint: 'distribuição' },
      ];
    },

    // ====================================================
    // CAMPAIGNS
    // ====================================================
    async createCampaign() {
      if (!this.newCampaign.name) return;
      try {
        await this.api('/api/campaigns', { method: 'POST', body: JSON.stringify(this.newCampaign) });
        this.newCampaign.name = ''; this.newCampaign.description = '';
        await this.loadCampaigns();
        window.bpToast?.('Campanha criada', 'success');
      } catch (e) { window.bpToast?.(e.message, 'error'); }
    },
    async deleteCampaign(id) {
      if (!confirm('Excluir campanha?')) return;
      await this.api('/api/campaigns/' + id, { method: 'DELETE' }); await this.loadCampaigns();
      window.bpToast?.('Campanha excluída', 'info');
    },

    // ====================================================
    // LEAD DRAWER
    // ====================================================
    openLead(l) { this.currentLead = { ...l }; this.leadOpen = true; },
    async patchLead(patch) {
      if (!this.currentLead) return;
      try {
        await this.api('/api/leads/' + this.currentLead.id, { method: 'PATCH', body: JSON.stringify(patch) });
        await this.loadLeads();
        if (this.tab === 'pipeline') this.loadPipeline();
        if (this.tab === 'today') this.loadToday();
      } catch (e) { window.bpToast?.(e.message, 'error'); }
    },
    async deleteLead() {
      if (!this.currentLead || !confirm('Excluir este lead?')) return;
      await this.api('/api/leads/' + this.currentLead.id, { method: 'DELETE' });
      this.leadOpen = false; this.currentLead = null;
      await this.loadLeads();
      window.bpToast?.('Lead excluído', 'info');
    },
    useAsLookalike() {
      if (!this.currentLead) return;
      this.lookalike.lead_id = this.currentLead.id;
      this.lookalike.source_input = this.currentLead.website || this.currentLead.name || '';
      this.lookalike.is_website = !!this.currentLead.website;
      this.lookalike.city = this.currentLead.city || '';
      this.lookalike.state = this.currentLead.state || '';
      this.leadOpen = false;
      this.tab = 'lookalike';
    },

    // ====================================================
    // HUNT
    // ====================================================
    async startHunt() {
      if (this.submittingHunt) return;
      if (!this.hunt.source_input?.trim()) {
        window.bpToast?.('Informe um site ou descrição', 'warn'); return;
      }
      this.submittingHunt = true;
      try {
        this.huntJob = null; this.analysis = null;
        const niches = (this.huntNiches || '').split(',').map(s => s.trim()).filter(Boolean);
        const payload = { ...this.hunt, manual_niches: niches };
        const r = await this.api('/api/hunt', { method: 'POST', body: JSON.stringify(payload) });
        saveHuntJobId(r.job_id);
        window.bpToast?.('Prospecção iniciada · roda em segundo plano', 'success');
        this.startPolling(r.job_id);
      } catch (e) { window.bpToast?.(e.message, 'error'); }
      finally { this.submittingHunt = false; }
    },

    async resumeJob(jobId) {
      try {
        const j = await this.api('/api/jobs/' + jobId);
        this.huntJob = j;
        if (j.status === 'running' || j.status === 'queued') this.startPolling(jobId);
        else saveHuntJobId(null);
      } catch { saveHuntJobId(null); }
    },

    startPolling(jobId) {
      if (this.pollHandle) clearInterval(this.pollHandle);
      const tick = async () => {
        try {
          const j = await this.api('/api/jobs/' + jobId);
          this.huntJob = j;
          if (j.status === 'done') {
            clearInterval(this.pollHandle); this.pollHandle = null;
            saveHuntJobId(null);
            const total = j.result?.total_leads ?? 0;
            window.bpToast?.(`Prospecção concluída · ${total} leads`, 'success', 6000);
            window.bpNotify?.('Brainy Prospect', `Sua prospecção terminou: ${total} leads encontrados.`);
            await this.refreshAll(); await this.loadCharts();
          } else if (j.status === 'error') {
            clearInterval(this.pollHandle); this.pollHandle = null;
            saveHuntJobId(null);
            window.bpToast?.('Prospecção falhou: ' + (j.error || 'erro'), 'error', 6000);
            window.bpNotify?.('Brainy Prospect', 'A prospecção falhou. Veja em Jobs.');
            await this.loadJobs();
          }
        } catch { clearInterval(this.pollHandle); this.pollHandle = null; saveHuntJobId(null); }
      };
      this.pollHandle = setInterval(tick, 1500); tick();
    },

    cancelTrackedHunt() {
      if (this.pollHandle) clearInterval(this.pollHandle);
      this.pollHandle = null; this.huntJob = null; saveHuntJobId(null);
      window.bpToast?.('Acompanhamento removido (job continua na aba Jobs)', 'info');
    },

    async analyze() {
      if (this.analyzing) return;
      this.analyzing = true; this.analysis = null;
      try {
        this.analysis = await this.api('/api/analyze', {
          method: 'POST',
          body: JSON.stringify({ source_input: this.hunt.source_input, is_website: this.hunt.is_website }),
        });
      } catch (e) { window.bpToast?.(e.message, 'error'); }
      finally { this.analyzing = false; }
    },

    // ====================================================
    // LOOKALIKE
    // ====================================================
    async startLookalike() {
      if (!this.lookalike.lead_id && !this.lookalike.source_input?.trim()) {
        window.bpToast?.('Informe um lead ou um site/descrição de referência', 'warn'); return;
      }
      try {
        const r = await this.api('/api/hunt-lookalike', { method: 'POST', body: JSON.stringify(this.lookalike) });
        saveHuntJobId(r.job_id);
        window.bpToast?.(`Lookalike iniciado para ${r.seed}`, 'success');
        this.startPolling(r.job_id);
        this.tab = 'jobs';
      } catch (e) { window.bpToast?.(e.message, 'error'); }
    },

    // ====================================================
    // OBJECTIONS
    // ====================================================
    async runObjection() {
      if (!this.objection.text.trim()) { window.bpToast?.('Escreva a objeção', 'warn'); return; }
      this.objectionLoading = true; this.objectionResult = null;
      try {
        this.objectionResult = await this.api('/api/objections', {
          method: 'POST',
          body: JSON.stringify({
            objection: this.objection.text,
            context: this.objection.context || null,
            lead_id: this.objection.lead_id || null,
          }),
        });
      } catch (e) { window.bpToast?.(e.message, 'error'); }
      finally { this.objectionLoading = false; }
    },
    copyText(t) {
      navigator.clipboard?.writeText(t || '').then(
        () => window.bpToast?.('Copiado!', 'success', 1600),
        () => window.bpToast?.('Falha ao copiar', 'error')
      );
    },

    // ====================================================
    // BRAINY CHAT
    // ====================================================
    async sendChat() {
      const msg = (this.chat.input || '').trim();
      if (!msg || this.chat.loading) return;
      this.chat.history.push({ role: 'user', content: msg });
      this.chat.input = ''; this.chat.loading = true;
      try {
        const r = await this.api('/api/brainy-chat', {
          method: 'POST',
          body: JSON.stringify({ message: msg, history: this.chat.history.slice(-8) }),
        });
        this.chat.history.push({ role: 'assistant', content: r.reply || '...' });
      } catch (e) {
        this.chat.history.push({ role: 'assistant', content: '⚠ ' + e.message });
      } finally { this.chat.loading = false; }
    },

    // ====================================================
    // PUSH / NOTIFICAÇÕES
    // ====================================================
    async enablePush() {
      const ok = await window.bpRequestNotify?.();
      if (ok) {
        this.pushOptIn = true;
        try { localStorage.setItem(PUSH_KEY, '1'); } catch {}
        window.bpToast?.('Notificações ativadas — você será avisado quando jobs terminarem.', 'success');
      } else {
        window.bpToast?.('Permissão negada pelo navegador.', 'warn');
      }
    },

    // ====================================================
    // TOUR (Driver.js)
    // ====================================================
    startTour() {
      if (!window.driver) return;
      const d = window.driver.js.driver({
        showProgress: true,
        nextBtnText: 'Próximo',
        prevBtnText: 'Voltar',
        doneBtnText: 'Fechar',
        steps: [
          { popover: { title: '👋 Bem-vindo à Brainy Prospect', description: 'Vou te mostrar em 30 segundos como tirar leads quentes ainda hoje.' } },
          { element: '[data-tour="today"]',     popover: { title: '🔥 Hoje', description: 'Seus leads mais quentes e o que fazer agora.' } },
          { element: '[data-tour="hunt"]',      popover: { title: '🚀 Prospectar', description: 'Cole um site ou descrição → IA gera nichos e busca empresas reais.' } },
          { element: '[data-tour="leads"]',     popover: { title: '👥 Leads', description: 'Toda sua base com filtros, mensagens prontas e exportações.' } },
          { element: '[data-tour="pipeline"]',  popover: { title: '🧭 Pipeline', description: 'Arraste os cards entre colunas para mover o lead no funil.' } },
          { element: '[data-tour="lookalike"]', popover: { title: '🪞 Lookalike', description: 'Pegue um cliente que fechou e ache outras empresas parecidas.' } },
          { element: '[data-tour="theme"]',     popover: { title: '🌗 Tema', description: 'Escolha claro ou escuro — fica salvo.' } },
          { popover: { title: '✅ Pronto!', description: 'Bora começar? Vai em "Prospectar".' } },
        ],
        onDestroyed: () => { try { localStorage.setItem(TOUR_KEY, '1'); } catch {} },
      });
      d.drive();
    },

    // ====================================================
    // helpers
    // ====================================================
    runningJobsCount() { return (this.jobs || []).filter(j => j.status === 'running' || j.status === 'queued').length; },
    isHuntRunning()    { return !!(this.huntJob && (this.huntJob.status === 'running' || this.huntJob.status === 'queued')); },

    async logout() {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
      saveHuntJobId(null);
      try { localStorage.removeItem('bp_tab'); } catch {}
      window.location.href = '/login';
    },

    fmtDate(s) {
      if (!s) return '';
      try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; }
    },
    statusLabel(s) {
      const m = { novo:'Novos', qualificado:'Qualificados', contatado:'Contatados', respondeu:'Responderam',
                  reuniao:'Reunião', proposta:'Proposta', fechado:'Fechados', perdido:'Perdidos' };
      return m[s] || s;
    },
  };
}
