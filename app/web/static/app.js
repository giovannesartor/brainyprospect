// ============================================================================
// Brainy Prospect — App Shell (Alpine component)
// - Persistência de jobs em background (não cancela ao trocar de aba)
// - Polling global, tema sincronizado, toasts
// ============================================================================

// Carrega user injetado pelo template
window.__USER__ = (function () {
  try {
    return JSON.parse(document.getElementById('__user_data__')?.textContent || '{}');
  } catch { return {}; }
})();

// Storage helpers — persiste o último jobId entre navegações/refreshes
const HUNT_JOB_KEY = 'bp_hunt_job_id';
const saveHuntJobId = (id) => { try { id ? localStorage.setItem(HUNT_JOB_KEY, id) : localStorage.removeItem(HUNT_JOB_KEY); } catch {} };
const loadHuntJobId = () => { try { return localStorage.getItem(HUNT_JOB_KEY); } catch { return null; } };

function appShell() {
  return {
    user: window.__USER__ || {},
    tab: localStorage.getItem('bp_tab') || 'dashboard',
    sidebarOpen: false,         // mobile drawer
    theme: localStorage.getItem('bp_theme') || 'dark',

    menu: [
      { id: 'dashboard', label: 'Dashboard',   icon: '📊' },
      { id: 'hunt',      label: 'Prospectar',  icon: '🚀' },
      { id: 'leads',     label: 'Leads',       icon: '👥' },
      { id: 'campaigns', label: 'Campanhas',   icon: '🎯' },
      { id: 'history',   label: 'Histórico',   icon: '🕘' },
      { id: 'jobs',      label: 'Jobs',        icon: '⚙️' },
    ],

    dash: {},
    leads: [],
    leadsFilters: { text: '', city: '', niche: '', status: '', priority: '' },
    campaigns: [],
    newCampaign: { name: '', description: '', target_mode: 'direct_sale', color: '#6366F1' },
    searches: [],
    jobs: [],

    // hunt
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

    // lead drawer
    leadOpen: false,
    currentLead: null,

    titles: {
      dashboard: ['Dashboard', 'Visão geral da operação'],
      hunt:      ['Nova prospecção', 'Site/descrição → leads qualificados'],
      leads:     ['Leads', 'Base completa com filtros'],
      campaigns: ['Campanhas', 'Agrupe leads por estratégia'],
      history:   ['Histórico', 'Buscas executadas'],
      jobs:      ['Jobs', 'Tarefas em background'],
    },
    currentTitle()    { return (this.titles[this.tab] || ['', ''])[0]; },
    currentSubtitle() { return (this.titles[this.tab] || ['', ''])[1]; },

    // ---------------- boot ----------------
    async boot() {
      // aplica tema
      this.applyTheme(this.theme);

      await this.refreshAll();

      // Restaura job em andamento (sobrevive a refresh/troca de aba/menu)
      const savedJobId = loadHuntJobId();
      if (savedJobId) await this.resumeJob(savedJobId);

      // Polling do dashboard sempre que o usuário estiver nele
      setInterval(() => { if (this.tab === 'dashboard') this.loadDashboard(); }, 30000);

      // Persistência de aba
      this.$watch('tab', v => { try { localStorage.setItem('bp_tab', v); } catch {} this.sidebarOpen = false; });
      this.$watch('theme', v => this.applyTheme(v));
    },

    setTab(id) {
      this.tab = id;
      this.sidebarOpen = false;
    },

    // ---------------- theme ----------------
    applyTheme(v) {
      try { localStorage.setItem('bp_theme', v); } catch {}
      document.documentElement.dataset.theme = v;
    },
    toggleTheme() {
      this.theme = (this.theme === 'dark') ? 'light' : 'dark';
    },

    // ---------------- data refresh ----------------
    async refreshAll() {
      await Promise.all([
        this.loadDashboard(), this.loadLeads(),
        this.loadCampaigns(), this.loadSearches(), this.loadJobs(),
      ]);
    },

    kpis() {
      const s = this.dash.stats || {};
      return [
        { label: 'Total leads',   value: s.total ?? 0,    hint: (s.today ?? 0) + ' hoje' },
        { label: 'Score médio',   value: s.avg_score ?? 0, hint: 'média global' },
        { label: 'Esta semana',   value: s.weekly ?? 0,    hint: 'últimos 7 dias' },
        { label: 'Direto/Parc.',  value: (s.direct_total ?? 0) + ' / ' + (s.partners_total ?? 0), hint: 'distribuição' },
      ];
    },

    // ---------------- API ----------------
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

    async loadDashboard() { try { this.dash = await this.api('/api/dashboard'); } catch (e) { console.warn(e); } },
    async loadLeads() {
      const q = new URLSearchParams();
      Object.entries(this.leadsFilters).forEach(([k, v]) => { if (v) q.set(k, v); });
      q.set('limit', 200);
      try { const r = await this.api('/api/leads?' + q.toString()); this.leads = r.items || []; } catch (e) { console.warn(e); }
    },
    async loadCampaigns() { try { this.campaigns = await this.api('/api/campaigns'); } catch (e) { console.warn(e); } },
    async loadSearches()  { try { this.searches  = await this.api('/api/searches?limit=50'); } catch (e) { console.warn(e); } },
    async loadJobs()      { try { this.jobs      = await this.api('/api/jobs'); } catch (e) { console.warn(e); } },

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

    openLead(l) { this.currentLead = { ...l }; this.leadOpen = true; },
    async patchLead(patch) {
      if (!this.currentLead) return;
      try {
        await this.api('/api/leads/' + this.currentLead.id, { method: 'PATCH', body: JSON.stringify(patch) });
        await this.loadLeads();
      } catch (e) { window.bpToast?.(e.message, 'error'); }
    },

    // ---------------- HUNT (background-safe) ----------------
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
      } catch (e) {
        window.bpToast?.(e.message, 'error');
      } finally {
        this.submittingHunt = false;
      }
    },

    // Retoma um job salvo (refresh ou navegação trouxe a página de volta)
    async resumeJob(jobId) {
      try {
        const j = await this.api('/api/jobs/' + jobId);
        this.huntJob = j;
        if (j.status === 'running' || j.status === 'queued') {
          this.startPolling(jobId);
        } else {
          // job já terminou; mantém na tela só se foi recente, mas remove o lock
          saveHuntJobId(null);
        }
      } catch {
        saveHuntJobId(null);
      }
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
            window.bpToast?.(`Prospecção concluída · ${j.result?.total_leads ?? 0} leads`, 'success', 6000);
            await this.refreshAll();
          } else if (j.status === 'error') {
            clearInterval(this.pollHandle); this.pollHandle = null;
            saveHuntJobId(null);
            window.bpToast?.('Prospecção falhou: ' + (j.error || 'erro'), 'error', 6000);
            await this.loadJobs();
          }
        } catch (e) {
          // se 404, job foi limpo; para o polling
          clearInterval(this.pollHandle); this.pollHandle = null; saveHuntJobId(null);
        }
      };
      this.pollHandle = setInterval(tick, 1500);
      tick();
    },

    cancelTrackedHunt() {
      // só limpa o tracking visual; o job continua rodando no servidor (e pode ser visto na aba Jobs)
      if (this.pollHandle) clearInterval(this.pollHandle);
      this.pollHandle = null;
      this.huntJob = null;
      saveHuntJobId(null);
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
      } catch (e) {
        window.bpToast?.(e.message, 'error');
      } finally {
        this.analyzing = false;
      }
    },

    // Indicadores globais (usado no header / sidebar)
    runningJobsCount() {
      return (this.jobs || []).filter(j => j.status === 'running' || j.status === 'queued').length;
    },
    isHuntRunning() {
      return !!(this.huntJob && (this.huntJob.status === 'running' || this.huntJob.status === 'queued'));
    },

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
  };
}
