function adminPanel() {
  return {
    user: (function(){ try { return JSON.parse(document.getElementById('__user_data__').textContent); } catch { return {}; } })(),
    tab: 'overview',
    sidebarOpen: false,
    menu: [
      {id:'overview',  label:'Visão geral',     icon:'📊'},
      {id:'activity',  label:'Atividade ao vivo', icon:'⚡'},
      {id:'metrics',   label:'Métricas',         icon:'📈'},
      {id:'users',     label:'Usuários',         icon:'👥'},
      {id:'ai',        label:'Inspetor de IA',   icon:'🧠'},
      {id:'scrapers',  label:'Buscas (scrapers)',icon:'🔎'},
      {id:'exports',   label:'Exports',          icon:'📤'},
      {id:'logins',    label:'Logins / Segurança', icon:'🔐'},
      {id:'errors',    label:'Erros',            icon:'⚠️'},
      {id:'feedback',  label:'Feedback',         icon:'💬'},
      {id:'settings',  label:'Configurações',    icon:'⚙️'},
      {id:'jobs',      label:'Jobs',             icon:'🔧'},
    ],
    titles: {
      overview: ['Visão geral','Saúde do sistema e estatísticas'],
      activity: ['Atividade ao vivo','Cada ação dos usuários em tempo real'],
      metrics:  ['Métricas','KPIs, top usuários, top buscas, custo de IA'],
      users:    ['Usuários','Aprovação, papéis, cotas e drill-down'],
      ai:       ['Inspetor de IA','Tokens, custo e prompts'],
      scrapers: ['Monitor de buscas','Saúde dos scrapers e queries'],
      exports:  ['Exports','Auditoria de downloads de leads'],
      logins:   ['Logins e segurança','Histórico de autenticação'],
      errors:   ['Erros','Telemetria de falhas (front e back)'],
      feedback: ['Feedback','Tickets enviados pelos usuários'],
      settings: ['Configurações globais','API keys, scraping e mensagens'],
      jobs:     ['Jobs do sistema','Tarefas em background'],
    },
    ov: {},
    users: [],
    userFilter: '',
    settings: {ai:{deepseek:{},openai:{}}, scraping:{}, app:{}, messages:{}},
    settingsSaved: false,
    adminJobs: [],
    activity: [],
    activityFilter: { user_id: '', action: '', q: '', since_minutes: 60 },
    activityAuto: true,
    online: [],
    metrics: null,
    aiUsage: [],
    aiFilter: { user_id: '', feature: '' },
    aiDetail: null,
    scraperRuns: [],
    scraperFilter: { source: '', only_failed: false },
    exports: [],
    logins: [],
    loginOnlyFailed: false,
    errors: [],
    errorDetail: null,
    feedback: [],
    feedbackFilter: '',
    selectedUser: null,

    async boot() {
      await Promise.all([this.loadOverview(), this.loadUsers(), this.loadSettings(), this.loadJobs()]);
      setInterval(()=> this.loadOverview(), 30000);
      setInterval(()=> { if(this.tab==='activity' && this.activityAuto) this.loadActivity(); }, 5000);
      setInterval(()=> { if(this.tab==='activity') this.loadOnline(); }, 15000);
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

    async loadOverview(){ try { this.ov = await this.api('/api/admin/overview'); } catch(e){ console.warn(e); } },
    async loadUsers(){
      const q = this.userFilter ? '?status='+this.userFilter : '';
      try { this.users = await this.api('/api/admin/users'+q); } catch(e){ console.warn(e); }
    },
    async loadSettings(){ try {
      const s = await this.api('/api/admin/settings');
      s.ai = s.ai || {deepseek:{},openai:{}};
      s.scraping = s.scraping || {};
      s.messages = s.messages || {};
      this.settings = s;
    } catch(e){ console.warn(e); } },
    async loadJobs(){ try { this.adminJobs = await this.api('/api/admin/jobs'); } catch(e){ console.warn(e); } },

    async loadActivity(){
      const f = this.activityFilter;
      const params = new URLSearchParams();
      if (f.user_id) params.set('user_id', f.user_id);
      if (f.action) params.set('action', f.action);
      if (f.q) params.set('q', f.q);
      if (f.since_minutes) params.set('since_minutes', f.since_minutes);
      params.set('limit', 200);
      try {
        const r = await this.api('/api/admin/activity?'+params.toString());
        this.activity = r.items || [];
      } catch(e){ console.warn(e); }
    },
    async loadOnline(){
      try { const r = await this.api('/api/admin/activity/online'); this.online = r.online || []; }
      catch(e){ console.warn(e); }
    },
    async loadMetrics(){
      try { this.metrics = await this.api('/api/admin/metrics?days=30'); }
      catch(e){ console.warn(e); }
    },
    async loadAI(){
      const f = this.aiFilter;
      const params = new URLSearchParams();
      if (f.user_id) params.set('user_id', f.user_id);
      if (f.feature) params.set('feature', f.feature);
      params.set('limit', 200);
      try { this.aiUsage = await this.api('/api/admin/ai-usage?'+params.toString()); }
      catch(e){ console.warn(e); }
    },
    async loadScrapers(){
      const f = this.scraperFilter;
      const params = new URLSearchParams();
      if (f.source) params.set('source', f.source);
      if (f.only_failed) params.set('only_failed', 'true');
      params.set('limit', 300);
      try { this.scraperRuns = await this.api('/api/admin/scraper-runs?'+params.toString()); }
      catch(e){ console.warn(e); }
    },
    async loadExports(){
      try { this.exports = await this.api('/api/admin/exports?limit=300'); }
      catch(e){ console.warn(e); }
    },
    async loadLogins(){
      const q = this.loginOnlyFailed ? '?only_failed=true' : '';
      try { this.logins = await this.api('/api/admin/login-events'+q); }
      catch(e){ console.warn(e); }
    },
    async loadErrors(){
      try { this.errors = await this.api('/api/admin/errors?limit=300'); }
      catch(e){ console.warn(e); }
    },
    async loadFeedback(){
      const q = this.feedbackFilter ? '?status='+this.feedbackFilter : '';
      try { this.feedback = await this.api('/api/admin/feedback'+q); }
      catch(e){ console.warn(e); }
    },
    async closeTicket(id){
      await this.api('/api/admin/feedback/'+id+'/close', {method:'POST'});
      await this.loadFeedback();
    },

    async openUserProfile(id){
      try { this.selectedUser = await this.api('/api/admin/users/'+id+'/profile'); }
      catch(e){ alert(e.message); }
    },
    closeUserProfile(){ this.selectedUser = null; },

    async impersonate(id){
      if (!confirm('Entrar como este usuário? Você será redirecionado para o app dele.')) return;
      try {
        await this.api('/api/admin/users/'+id+'/impersonate', {method:'POST'});
        window.location.href = '/app';
      } catch(e){ alert(e.message); }
    },

    async approveUser(id){ await this.api('/api/admin/users/'+id+'/approve', {method:'POST'}); await this.loadUsers(); await this.loadOverview(); },
    async blockUser(id){ if(!confirm('Bloquear usuário?')) return; await this.api('/api/admin/users/'+id+'/block', {method:'POST'}); await this.loadUsers(); },
    async deleteUser(id){ if(!confirm('Excluir usuário definitivamente?')) return; await this.api('/api/admin/users/'+id, {method:'DELETE'}); await this.loadUsers(); },
    async toggleRole(u){
      const role = u.role === 'admin' ? 'user' : 'admin';
      await this.api('/api/admin/users/'+u.id, {method:'PATCH', body: JSON.stringify({role})}); await this.loadUsers();
    },
    async resetPassword(u){
      const pw = prompt('Nova senha para '+u.email+':');
      if (!pw || pw.length < 6) return alert('Senha mínima de 6 caracteres.');
      await this.api('/api/admin/users/'+u.id+'/reset-password', {method:'POST', body: JSON.stringify({new_password: pw})});
      alert('Senha redefinida.');
    },
    async setQuotas(u){
      const s = prompt('Buscas/dia (vazio = sem limite):', u.quota_searches_per_day ?? '');
      if (s === null) return;
      const e = prompt('Exports/dia (vazio = sem limite):', u.quota_exports_per_day ?? '');
      if (e === null) return;
      const a = prompt('Chamadas IA/dia (vazio = sem limite):', u.quota_ai_per_day ?? '');
      if (a === null) return;
      const body = {
        quota_searches_per_day: s==='' ? null : Number(s),
        quota_exports_per_day:  e==='' ? null : Number(e),
        quota_ai_per_day:       a==='' ? null : Number(a),
      };
      await this.api('/api/admin/users/'+u.id, {method:'PATCH', body: JSON.stringify(body)});
      await this.loadUsers();
    },

    async saveSettings(){
      const patch = { ai: this.settings.ai, scraping: this.settings.scraping, messages: this.settings.messages, app: this.settings.app };
      ['deepseek','openai'].forEach(p => {
        if (patch.ai[p]) delete patch.ai[p].api_key_masked;
        if (patch.ai[p] && !patch.ai[p].api_key) delete patch.ai[p].api_key;
      });
      try {
        await this.api('/api/admin/settings', {method:'PATCH', body: JSON.stringify(patch)});
        this.settingsSaved = true;
        setTimeout(()=> this.settingsSaved = false, 2500);
        await this.loadSettings();
      } catch(e){ alert(e.message); }
    },

    async cleanupJobs(){
      const r = await this.api('/api/admin/jobs/cleanup', {method:'POST'});
      alert(r.removed + ' jobs antigos removidos.');
      await this.loadJobs();
    },

    async logout(){
      await fetch('/api/auth/logout', {method:'POST', credentials:'include'});
      window.location.href = '/login';
    },

    fmtDate(s){ if(!s) return '—'; try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; } },
    fmtTime(s){ if(!s) return '—'; try { return new Date(s).toLocaleTimeString('pt-BR'); } catch { return s; } },
    fmtCurrency(n){ if(n==null) return '$0.00'; return '$'+Number(n).toFixed(4); },
    fmtNumber(n){ return new Intl.NumberFormat('pt-BR').format(n||0); },
    actionBadge(a){
      const map = {
        login_attempt:'badge-info', register:'badge-success', logout:'badge-info',
        hunt_start:'badge-warn', lookalike_start:'badge-warn',
        export:'badge-danger', impersonate:'badge-danger',
        ai_chat:'badge-info', ai_objection:'badge-info', analyze:'badge-info',
        lead_update:'', lead_delete:'badge-danger',
      };
      return map[a] || '';
    },

    onTabChange(t){
      this.tab = t; this.sidebarOpen = false;
      if (t==='activity') { this.loadActivity(); this.loadOnline(); }
      if (t==='metrics')  this.loadMetrics();
      if (t==='ai')       this.loadAI();
      if (t==='scrapers') this.loadScrapers();
      if (t==='exports')  this.loadExports();
      if (t==='logins')   this.loadLogins();
      if (t==='errors')   this.loadErrors();
      if (t==='feedback') this.loadFeedback();
    },
  };
}
