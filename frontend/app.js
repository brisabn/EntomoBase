const { createApp } = Vue;

createApp({
  data() {
    return {
      apiUrl: 'http://127.0.0.1:8000',
      abaAtiva: 'projetos',
      termoBusca: '', filtroAno: null, filtroGrupo: '', filtroFinalizado: null, filtroLocal: '',
      formProjeto: false, formEspecime: false, showLogin: false,
      projetos: [], especimes: [], token: null, userEmail: null, loginError: null,
      credenciais: { email: '', senha: '' },
      novoProjeto: { id: null, titulo: '', ano: 2026, grupo_insetos: '', tracos_medidos: '', local_coleta: '', capa_url: '', dataset_externo_url: '', publicacao_vinculada: '', finalizado: true },
      novoEspecime: { codigo_etiqueta: '', grupo_insetos: '', especie: '', projeto_id: null, largura_pronoto_mm: null, tamanho_chifre_mm: null, local_coleta: '', fotografia_url: '' },
      equipe: [
        { nome: 'Brisa Barbosa', papel: 'Desenvolvimento e Modelagem', foto: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200' },
        { nome: 'Douglas Maciel', papel: 'Pesquisador Responsável', foto: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200' },
        { nome: 'Mateus Krause', papel: 'Modelagem Matemática', foto: 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=200' }
      ]
    };
  },
  computed: {
    acessoLab() { return !!this.token; },
    projetosFiltrados() {
      const q = this.termoBusca.toLowerCase().trim();
      if (!q) return this.projetos;
      return this.projetos.filter(p => p.titulo.toLowerCase().includes(q) || p.grupo_insetos.toLowerCase().includes(q) || (p.local_coleta && p.local_coleta.toLowerCase().includes(q)));
    },
    arvoreColecao() {
      const q = this.termoBusca.toLowerCase().trim();
      const arvore = {};
      this.especimes.forEach(esp => {
        if (q && !esp.especie.toLowerCase().includes(q) && !esp.grupo_insetos.toLowerCase().includes(q) && !(esp.local_coleta && esp.local_coleta.toLowerCase().includes(q))) return;
        if (!arvore[esp.grupo_insetos]) arvore[esp.grupo_insetos] = {};
        if (!arvore[esp.grupo_insetos][esp.especie]) arvore[esp.grupo_insetos][esp.especie] = [];
        arvore[esp.grupo_insetos][esp.especie].push(esp);
      });
      return arvore;
    }
  },
  async mounted() {
    this.token = localStorage.getItem('entomobase_token');
    this.userEmail = localStorage.getItem('entomobase_email');
    await this.carregarProjetos();
    await this.carregarEspecimes();
  },
  methods: {
    headersAuth() { return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` }; },
    async fazerLogin() {
      this.loginError = null;
      const res = await fetch(`${this.apiUrl}/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.credenciais) });
      if (res.ok) {
        const data = await res.json();
        this.token = data.access_token; this.userEmail = data.email;
        localStorage.setItem('entomobase_token', this.token); localStorage.setItem('entomobase_email', this.userEmail);
        this.showLogin = false; this.credenciais = { email: '', senha: '' };
        await this.carregarProjetos();
      } else { this.loginError = 'Credenciais inválidas.'; }
    },
    fazerLogout() {
      this.token = null; this.userEmail = null;
      localStorage.removeItem('entomobase_token'); localStorage.removeItem('entomobase_email');
      this.carregarProjetos();
    },
    contarPorGrupo(espMap) { return Object.values(espMap).reduce((acc, l) => acc + l.length, 0); },
    resetFormProjeto() { this.novoProjeto = { id: null, titulo: '', ano: 2026, grupo_insetos: '', tracos_medidos: '', local_coleta: '', capa_url: '', dataset_externo_url: '', publicacao_vinculada: '', finalizado: true }; },
    editarProjeto(p) { this.novoProjeto = { ...p }; this.formProjeto = true; window.scrollTo(0, 0); },
    async carregarProjetos() {
      const params = new URLSearchParams({ acesso_laboratorio: this.acessoLab });
      if (this.filtroAno) params.append('ano', this.filtroAno);
      if (this.filtroGrupo.trim()) params.append('grupo_insetos', this.filtroGrupo.trim());
      if (this.filtroLocal.trim()) params.append('local_coleta', this.filtroLocal.trim());
      if (this.acessoLab && this.filtroFinalizado !== null) params.append('finalizado', this.filtroFinalizado);
      const res = await fetch(`${this.apiUrl}/projetos?${params.toString()}`);
      if (res.ok) this.projetos = await res.json();
    },
    async carregarEspecimes() { const res = await fetch(`${this.apiUrl}/especimes`); if (res.ok) this.especimes = await res.json(); },
    async salvarProjeto() {
      const url = this.novoProjeto.id ? `${this.apiUrl}/projetos/${this.novoProjeto.id}` : `${this.apiUrl}/projetos`;
      const method = this.novoProjeto.id ? 'PUT' : 'POST';
      const payload = { ...this.novoProjeto }; delete payload.id;
      const res = await fetch(url, { method, headers: this.headersAuth(), body: JSON.stringify(payload) });
      if (res.ok) { this.formProjeto = false; this.resetFormProjeto(); await this.carregarProjetos(); }
    },
    async apagarProjeto(id) {
      if(confirm('Apagar este projeto e todos os seus espécimes?')){
        const res = await fetch(`${this.apiUrl}/projetos/${id}`, { method: 'DELETE', headers: this.headersAuth() });
        if (res.ok) { await this.carregarProjetos(); await this.carregarEspecimes(); }
      }
    },
    async salvarEspecime() {
      const payload = { ...this.novoEspecime, medicoes: [{ largura_pronoto_mm: this.novoEspecime.largura_pronoto_mm, tamanho_chifre_mm: this.novoEspecime.tamanho_chifre_mm ?? null }] };
      const res = await fetch(`${this.apiUrl}/especimes`, { method: 'POST', headers: this.headersAuth(), body: JSON.stringify(payload) });
      if (res.ok) { this.formEspecime = false; this.novoEspecime = { codigo_etiqueta: '', grupo_insetos: '', especie: '', projeto_id: null, largura_pronoto_mm: null, tamanho_chifre_mm: null, local_coleta: '', fotografia_url: '' }; await this.carregarEspecimes(); await this.carregarProjetos(); }
    },
    async removerEspecime(id) { const res = await fetch(`${this.apiUrl}/especimes/${id}`, { method: 'DELETE', headers: this.headersAuth() }); if (res.ok) { await this.carregarEspecimes(); await this.carregarProjetos(); } }
  }
}).mount('#app');