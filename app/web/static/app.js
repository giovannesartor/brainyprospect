function appShell() {
  return {
    user: window.__USER__ || {},
    tab: 'dashboard',
    menu: [
      {id:'dashboard', label:'Dashboard', icon:'📊'},
      {id:'hunt',      label:'Prospectar', icon:'🚀'},
      {id:'leads',     label:'Leads', icon:'👥'},
      {id:'campaigns', label:'Campanhas', icon:'🎯'},
      {id:'history',   label:'Histórico', icon:'🕘'},
      {id:'jobs',      label:'Jobs', icon:'⚙️'},
    ],
    dash: {},
    leads: [],
    leadsFilters: {text:'', city:'', niche:'', status:'', priority:''},
    campaigns: [],
    newCampaign: {name:'', description:'', target_mode:'direct_sale', color:'#6366F1'},
    searches: [],
    jobs: [],
    hunt: {source_input:'', is_website:false, manual_niches:[], city:'', state:'', country:'Brasil', max_per_niche:15, use_ai_qualification:true, mode:'direct_sale'},
    huntNiches: '',
    huntJob: null,
    pollHandle: null,
    analysis: null,
    leadOpen: false,
    currentLead: null,

    async boot() {
      await this.refreshAll();
      setInterval(() => { if (this.tab==='dashboard') this.loadDashboard(); }, 30000);
    },
    async refreshAll() {
      await Promise.all([this.loadDashboard(), this.loadLeads(), this.loadCampaigns(), this.loadSearches(), this.loadJobs()]);
    },
    titles: {
      dashboard:['Dashboard','Visão geral da operação'],
      hunt:['Nova prospecção','Site/descrição → leads qualificados'],
      leads:['Leads','Base completa com filtros'],
      campaigns:['Campanhas','Agrupe leads por estratégia'],
      history:['Histórico','Buscas executadas'],
      jobs:['Jobs','Tarefas em background'],
    },
    currentTitle(){ return (this.titles[this.tab]||['',''])[0]; },
    currentSubtitle(){ return (this.titles[this.tab]||['',''])[1]; },

    kpis() {
      const s = this.dash.stats || {};
      return [
        {label:'Total leads',  value: s.total ?? 0, hint: (s.today??0)+' hoje'},
        {label:'Score médio',  value: s.avg_score ?? 0, hint: 'média global'},
        {label:'Esta semana',  value: s.weekly ?? 0, hint: 'últimos 7 dias'},
        {label:'Direto/Parc.', value: (s.direct_total??0)+' / '+(s.partners_total??0), hint: 'distribuição'},
      ];
    },

    async api(path, opts={}) {
      const res = await fetch(path, {credentials:'include', headers:{'Content-Type':'application/json',...(opts.headers||{})}, ...opts});
      if (res.status === 401) { window.location.href='/login'; throw new Error('401'); }
      if (!res.ok) {
        const err = await res.json().catch(()=>({detail:res.statusText}));
        throw new Error(err.detail || ('HTTP '+res.status));
      }
      return res.json();
    },

    async loadDashboard(){ try { this.dash = await this.api('/api/dashboard'); } catch(e){ console.warn(e); } },
    async loadLeads(){
      const q = new URLSearchParams();
      Object.entries(this.leadsFilters).forEach(([k,v]) => { if (v) q.set(k,v); });
      q.set('limit', 200);
      try { const r = await this.api('/api/leads?'+q.toString()); this.leads = r.items || []; } catch(e){ console.warn(e); }
    },
    async loadCampaigns(){ try { this.campaigns = await this.api('/api/campaigns'); } catch(e){ console.warn(e); } },
    async loadSearches(){ try { this.searches = await this.api('/api/searches?limit=50'); } catch(e){ console.warn(e); } },
    async loadJobs(){ try { this.jobs = await this.api('/api/jobs'); } catch(e){ console.warn(e); } },

    async createCampaign(){
      if (!this.newCampaign.name) return;
      try { await this.api('/api/campaigns', {method:'POST', body: JSON.stringify(this.newCampaign)}); this.newCampaign.name=''; await this.loadCampaigns(); }
      catch(e){ alert(e.message); }
    },
    async deleteCampaign(id){
      if (!confirm('Excluir campanha?')) return;
      await this.api('/api/campaigns/'+id, {method:'DELETE'}); await this.loadCampaigns();
    },

    openLead(l){ this.currentLead = {...l}; this.leadOpen = true; },
    async patchLead(patch){
      if (!this.currentLead) return;
      await this.api('/api/leads/'+this.currentLead.id, {method:'PATCH', body: JSON.stringify(patch)});
      await this.loadLeads();
    },

    async startHunt(){
      this.huntJob = null; this.analysis = null;
      const niches = (this.huntNiches||'').split(',').map(s=>s.trim()).filter(Boolean);
      const payload = {...this.hunt, manual_niches: niches};
      const r = await this.api('/api/hunt', {method:'POST', body: JSON.stringify(payload)});
      this.pollJob(r.job_id);
    },
    async pollJob(jobId){
      if (this.pollHandle) clearInterval(this.pollHandle);
      const fn = async () => {
        try {
          const j = await this.api('/api/jobs/'+jobId);
          this.huntJob = j;
          if (j.status === 'done' || j.status === 'error') {
            clearInterval(this.pollHandle); this.pollHandle = null;
            await this.refreshAll();
          }
        } catch(e){ clearInterval(this.pollHandle); }
      };
      this.pollHandle = setInterval(fn, 1500);
      fn();
    },
    async analyze(){
      this.analysis = null;
      try {
        const r = await this.api('/api/analyze', {method:'POST', body: JSON.stringify({source_input: this.hunt.source_input, is_website: this.hunt.is_website})});
        this.analysis = r;
      } catch(e){ alert(e.message); }
    },

    async logout(){
      await fetch('/api/auth/logout', {method:'POST', credentials:'include'});
      window.location.href = '/login';
    },

    fmtDate(s){
      if (!s) return '';
      try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; }
    },
  };
}

// Injeta user do template
window.__USER__ = (function(){
  try {
    return JSON.parse(document.getElementById('__user_data__')?.textContent || '{}');
  } catch { return {}; }
})();
