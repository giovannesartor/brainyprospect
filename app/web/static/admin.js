function adminPanel() {
  return {
    user: (function(){ try { return JSON.parse(document.getElementById('__user_data__').textContent); } catch { return {}; } })(),
    tab: 'overview',
    sidebarOpen: false,
    menu: [
      {id:'overview', label:'Visão geral', icon:'📊'},
      {id:'users',    label:'Usuários', icon:'👥'},
      {id:'settings', label:'Configurações', icon:'⚙️'},
      {id:'jobs',     label:'Jobs', icon:'🔧'},
    ],
    titles: {
      overview: ['Visão geral','Saúde do sistema e estatísticas'],
      users:    ['Usuários','Aprovação, papéis e bloqueio'],
      settings: ['Configurações globais','API keys, scraping e mensagens'],
      jobs:     ['Jobs do sistema','Tarefas em background'],
    },
    ov: {},
    users: [],
    userFilter: '',
    settings: {ai:{deepseek:{},openai:{}}, scraping:{}, app:{}, messages:{}},
    settingsSaved: false,
    adminJobs: [],

    async boot() {
      await Promise.all([this.loadOverview(), this.loadUsers(), this.loadSettings(), this.loadJobs()]);
      setInterval(()=> this.loadOverview(), 30000);
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
      // garante seções
      s.ai = s.ai || {deepseek:{},openai:{}};
      s.scraping = s.scraping || {};
      s.messages = s.messages || {};
      this.settings = s;
    } catch(e){ console.warn(e); } },
    async loadJobs(){ try { this.adminJobs = await this.api('/api/admin/jobs'); } catch(e){ console.warn(e); } },

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

    async saveSettings(){
      // monta patch — remove chaves vazias para não sobrescrever
      const patch = {
        ai: this.settings.ai,
        scraping: this.settings.scraping,
        messages: this.settings.messages,
        app: this.settings.app,
      };
      // limpa api_key_masked
      ['deepseek','openai'].forEach(p => {
        if (patch.ai[p]) delete patch.ai[p].api_key_masked;
        if (patch.ai[p] && !patch.ai[p].api_key) delete patch.ai[p].api_key; // não sobrescreve com vazio
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
  };
}
