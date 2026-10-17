const { createApp } = Vue;

createApp({
  data() {
    return {
      apiUrl: 'http://127.0.0.1:8000',
      especimes: [],
      projetos: [],
      filtroEspecie: '',
      erro: null,
      novoProjeto: {
        titulo: '',
        publicacao_vinculada: ''
      },
      novoEspecime: {
        codigo_etiqueta: '',
        especie: '',
        projeto_id: null,
        largura_pronoto_mm: null,
        tamanho_chifre_mm: null,
        latitude: null,
        longitude: null,
        fotografia_url: '',
        notas: ''
      }
    };
  },
  mounted() {
    this.carregarProjetos();
    this.carregarEspecimes();
  },
  methods: {
    async carregarProjetos() {
      try {
        const res = await fetch(`${this.apiUrl}/projetos`);
        this.projetos = await res.json();
      } catch (e) {
        this.erro = 'Erro ao conectar com a API para listar projetos.';
      }
    },
    async carregarEspecimes() {
      try {
        this.erro = null;
        let url = `${this.apiUrl}/especimes`;
        if (this.filtroEspecie.trim() !== '') {
          url += `?especie=${encodeURIComponent(this.filtroEspecie.trim())}`;
        }
        const res = await fetch(url);
        this.especimes = await res.json();
      } catch (e) {
        this.erro = 'Erro ao carregar espécimes do acervo.';
      }
    },
    async salvarProjeto() {
      try {
        this.erro = null;
        const res = await fetch(`${this.apiUrl}/projetos`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.novoProjeto)
        });
        if (!res.ok) throw new Error('Falha ao criar projeto');
        this.novoProjeto = { titulo: '', publicacao_vinculada: '' };
        await this.carregarProjetos();
      } catch (e) {
        this.erro = e.message;
      }
    },
    async salvarEspecime() {
      try {
        this.erro = null;
        const payload = {
          codigo_etiqueta: this.novoEspecime.codigo_etiqueta,
          especie: this.novoEspecime.especie,
          projeto_id: this.novoEspecime.projeto_id,
          latitude: this.novoEspecime.latitude || null,
          longitude: this.novoEspecime.longitude || null,
          fotografia_url: this.novoEspecime.fotografia_url || null,
          notas: this.novoEspecime.notas || null,
          medicoes: [{
            largura_pronoto_mm: this.novoEspecime.largura_pronoto_mm,
            tamanho_chifre_mm: this.novoEspecime.tamanho_chifre_mm ?? null
          }]
        };
        const res = await fetch(`${this.apiUrl}/especimes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Erro ao salvar espécime');
        }
        this.novoEspecime = { codigo_etiqueta: '', especie: '', projeto_id: null, largura_pronoto_mm: null, tamanho_chifre_mm: null, latitude: null, longitude: null, fotografia_url: '', notas: '' };
        await this.carregarEspecimes();
      } catch (e) {
        this.erro = e.message;
      }
    },
    async removerEspecime(id) {
      await fetch(`${this.apiUrl}/especimes/${id}`, { method: 'DELETE' });
      await this.carregarEspecimes();
    }
  }
}).mount('#app');