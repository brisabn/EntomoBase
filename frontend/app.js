const { createApp, markRaw } = Vue;

const PALETA_CAPAS = ['#c9d9a2', '#e9b78a', '#e3b9a3', '#b8cfc0'];
const CORES_ORDEM = ['#c8762b', '#4f7a3a', '#8a4f7d', '#2f6f8f', '#b04a3a', '#7a6a2a'];
const POR_PAGINA_GALERIA = 48;

const ICONES = {
  externo: '<path d="M7 17 17 7M8.5 7H17v8.5"/>',
  voltar: '<path d="M19 12H5m6-6-6 6 6 6"/>',
  esq: '<path d="m15 5-7 7 7 7"/>',
  dir: '<path d="m9 5 7 7-7 7"/>',
  fechar: '<path d="M6 6l12 12M18 6 6 18"/>'
};

const norm = (s) => (s ?? '').toString().normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const ehUrl = (s) => /^https?:\/\//i.test((s || '').trim());
const nulo = (s) => ((s ?? '').toString().trim() || null);
const num = (v) => (v === '' || v === null || v === undefined || Number.isNaN(v) ? null : Number(v));
const cmp = (a, b) => a.localeCompare(b, 'pt-BR');
const fmt = (v) => Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
const SEM_FAMILIA = 'Sem família';

function tokenValido(token) {
  if (!token) return false;
  try {
    const corpo = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return !corpo.exp || corpo.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

function contarPor(lista, chaveFn) {
  const mapa = new Map();
  lista.forEach((e) => {
    const k = chaveFn(e);
    if (!mapa.has(k)) mapa.set(k, new Set());
    mapa.get(k).add(e.especie);
  });
  return mapa;
}

// ------------------------------------------------------------------ CSV
function lerCsv(texto) {
  texto = texto.replace(/^﻿/, '');
  const primeira = texto.split(/\r?\n/, 1)[0] || '';
  const delim = [';', '\t', ','].map((d) => [d, primeira.split(d).length]).sort((a, b) => b[1] - a[1])[0][0];
  const linhas = [];
  let campo = '';
  let linha = [];
  let aspas = false;
  const fechar = () => {
    linha.push(campo);
    campo = '';
    if (linha.some((x) => x.trim() !== '')) linhas.push(linha);
    linha = [];
  };
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (aspas) {
      if (c === '"') {
        if (texto[i + 1] === '"') { campo += '"'; i++; } else aspas = false;
      } else campo += c;
    } else if (c === '"') aspas = true;
    else if (c === delim) { linha.push(campo); campo = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && texto[i + 1] === '\n') i++; fechar(); }
    else campo += c;
  }
  if (campo !== '' || linha.length) fechar();
  return linhas;
}

const ALIASES = {
  codigo_etiqueta: ['codigo_etiqueta', 'codigo', 'etiqueta', 'cod', 'id_etiqueta', 'tombo'],
  grupo_insetos: ['ordem', 'grupo', 'grupo_insetos', 'order'],
  familia: ['familia', 'family'],
  especie: ['especie', 'species', 'nome_cientifico'],
  data_coleta: ['data_coleta', 'data', 'data_da_coleta', 'date'],
  local_coleta: ['local_coleta', 'local', 'localidade'],
  latitude: ['latitude', 'lat'],
  longitude: ['longitude', 'lon', 'lng', 'long'],
  altitude_m: ['altitude', 'altitude_m', 'alt'],
  sexo: ['sexo', 'sex'],
  estagio: ['estagio', 'estadio', 'casta'],
  imagem_arquivo: ['imagem', 'imagem_arquivo', 'arquivo_imagem', 'arquivo', 'foto', 'imagem_zenodo'],
  fotografia_url: ['fotografia_url', 'url_imagem', 'foto_url'],
  notas: ['notas', 'observacoes', 'obs', 'observacao'],
  projeto: ['projeto', 'titulo_projeto'],
  projeto_id: ['projeto_id', 'id_projeto']
};
const CAMPOS_IMPORTACAO = [
  ['codigo_etiqueta', 'Código da etiqueta'], ['grupo_insetos', 'Ordem'], ['familia', 'Família'], ['especie', 'Espécie'],
  ['data_coleta', 'Data da coleta'], ['local_coleta', 'Local de coleta'], ['latitude', 'Latitude'], ['longitude', 'Longitude'],
  ['altitude_m', 'Altitude (m)'], ['sexo', 'Sexo'], ['estagio', 'Estágio'], ['imagem_arquivo', 'Arquivo da imagem'],
  ['fotografia_url', 'URL da fotografia'], ['notas', 'Notas'], ['projeto', 'Projeto (título)'], ['projeto_id', 'Projeto (id)']
];

function chaveCabecalho(h) {
  return norm(h.replace(/\([^)]*\)/g, '')).replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function interpretarCabecalho(h) {
  const chave = chaveCabecalho(h);
  for (const [campo, nomes] of Object.entries(ALIASES)) {
    if (nomes.includes(chave)) return { destino: `campo:${campo}`, traco: '', unidade: 'mm' };
  }
  if (chave === 'id') return { destino: 'ignorar', traco: '', unidade: 'mm' };
  const m = /\(([^)]*)\)\s*$/.exec(h);
  return { destino: 'medida', traco: h.replace(/\([^)]*\)\s*$/, '').trim(), unidade: m && m[1].trim() ? m[1].trim() : 'mm' };
}

function numeroBr(v) {
  const t = String(v).trim().replace(/\s/g, '').replace(',', '.');
  return t !== '' && Number.isFinite(Number(t)) ? Number(t) : NaN;
}

function dataIso(v) {
  const t = String(v).trim();
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(t);
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  m = /^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/.exec(t);
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  return t;
}

// ------------------------------------------------------------------ Zenodo
// as regras de montagem das URLs ficam todas aqui, para ajustar fácil se o Zenodo mudar
const Zenodo = {
  idDoRegistro(url) {
    const t = url || '';
    const m = /zenodo\.org\/records?\/(\d+)/i.exec(t) || /10\.5281\/zenodo\.(\d+)/i.exec(t);
    return m ? m[1] : null;
  },
  // ids que começam com 0 são fictícios (o Zenodo nunca usa); as imagens vêm da rota /demo da API
  ehDemo(id) { return !!id && id.startsWith('0'); },
  miniatura(id, arquivo, largura) {
    return `https://zenodo.org/api/iiif/record:${id}:${encodeURIComponent(arquivo)}/full/${largura},/0/default.jpg`;
  },
  arquivo(id, arquivo) {
    return `https://zenodo.org/records/${id}/files/${encodeURIComponent(arquivo)}`;
  }
};

const app = createApp({
  data() {
    return {
      apiUrl: 'http://127.0.0.1:8000',
      rota: { nome: 'sobre' },
      termoBusca: '',
      buscaColecao: '',
      sugAberta: false,
      idxSug: -1,
      ordenacao: 'recentes',
      opcoesOrdem: [
        { valor: 'recentes', rotulo: 'Mais recentes' },
        { valor: 'titulo', rotulo: 'Título (A-Z)' },
        { valor: 'especies', rotulo: 'Mais espécies' }
      ],
      carregando: true,
      erroApi: null,
      projetos: [],
      especimes: [],
      token: null,
      userEmail: null,
      showLogin: false,
      loginErro: null,
      credenciais: { email: '', senha: '' },
      enviando: false,
      menuAberto: null,
      popover: null,
      filtros: { ano: null, grupo: null, status: null, local: null },
      colecaoFiltros: { ordens: [], familias: [], repos: [], anos: [] },
      familiasAbertas: false,
      filtrosMobileAbertos: false,
      abertos: {},
      limiteGaleria: POR_PAGINA_GALERIA,
      painel: null,
      mapaFoco: null,
      formProjeto: null,
      formEspecime: null,
      importacao: null,
      erroForm: null,
      confirmacao: null,
      info: null,
      toast: null,
      filtrosProjeto: [
        { chave: 'ano', rotulo: 'Ano' },
        { chave: 'grupo', rotulo: 'Grupo' },
        { chave: 'status', rotulo: 'Status' },
        { chave: 'local', rotulo: 'Local' }
      ],
      abas: [
        { id: 'sobre', rotulo: 'Sobre', href: '#/sobre' },
        { id: 'projetos', rotulo: 'Projetos', href: '#/projetos' },
        { id: 'colecao', rotulo: 'Coleção', href: '#/colecao' }
      ],
      textoSobre: '[Texto: o que é a EntomoBase, quem mantém, objetivo científico e como os dados são organizados.]',
      contato: '[e-mail de contato]',
      camposImportacao: CAMPOS_IMPORTACAO,
      equipe: [
        { iniciais: 'NS', nome: '[Nome Sobrenome]', papel: 'Graduando em Ciências Biológicas (UFMG)' },
        { iniciais: 'NS', nome: '[Nome Sobrenome]', papel: 'Graduando em Ciências Biológicas (UFMG)' },
        { iniciais: 'NS', nome: '[Nome Sobrenome]', papel: 'Graduando em Ciências Biológicas (UFMG)' }
      ]
    };
  },

  computed: {
    acessoLab() { return !!this.token; },
    abaAtiva() { return this.rota.nome === 'projeto' ? 'projetos' : this.rota.nome; },
    visaoColecao() { return this.rota.visao || 'arvore'; },
    vistaProjeto() { return this.rota.vista || 'tabela'; },
    contatoEhEmail() { return /^[^\s@\[\]]+@[^\s@\[\]]+\.[^\s@\[\]]+$/.test(this.contato); },

    textoCitacao() {
      const data = new Date().toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' });
      return `EntomoBase. Universidade Federal de Minas Gerais. Disponível em: ${location.href.split('#')[0]}. Acesso em: ${data}.`;
    },

    tituloPagina() {
      const nomes = { sobre: 'Sobre', projetos: 'Projetos', colecao: 'Coleção', busca: 'Busca' };
      if (this.rota.nome === 'projeto') {
        return this.projetoAtual ? `${this.projetoAtual.titulo} · EntomoBase` : 'Projeto · EntomoBase';
      }
      return `${nomes[this.rota.nome]} · EntomoBase`;
    },

    // ---------- dados base ----------
    projetosPorId() {
      const mapa = {};
      this.projetos.forEach((p) => { mapa[p.id] = p; });
      return mapa;
    },
    especimesPorId() {
      const mapa = {};
      this.especimes.forEach((e) => { mapa[e.id] = e; });
      return mapa;
    },
    especimesPorProjeto() {
      const mapa = {};
      this.especimes.forEach((e) => {
        if (e.projeto_id === null || e.projeto_id === undefined) return;
        (mapa[e.projeto_id] = mapa[e.projeto_id] || []).push(e);
      });
      return mapa;
    },
    coresOrdem() {
      const ordens = [...new Set(this.especimes.map((e) => e.grupo_insetos))].sort(cmp);
      const mapa = {};
      ordens.forEach((o, i) => { mapa[o] = CORES_ORDEM[i % CORES_ORDEM.length]; });
      return mapa;
    },

    // ---------- projetos ----------
    projetoAtual() {
      return this.rota.nome === 'projeto' ? (this.projetosPorId[this.rota.id] || null) : null;
    },
    especimesDoProjeto() {
      const p = this.projetoAtual;
      if (!p) return [];
      return [...(this.especimesPorProjeto[p.id] || [])].sort((a, b) => cmp(a.codigo_etiqueta, b.codigo_etiqueta));
    },
    colunasMedidas() {
      const colunas = [];
      this.especimesDoProjeto.forEach((e) => (e.medidas || []).forEach((m) => {
        const chave = `${m.traco}|${m.unidade}`;
        if (!colunas.some((c) => c.chave === chave)) colunas.push({ chave, traco: m.traco, unidade: m.unidade });
      }));
      return colunas;
    },
    opcoesFiltro() {
      const unicos = (fn) => [...new Set(this.projetos.map(fn).filter((v) => v !== null && v !== undefined && v !== ''))];
      const status = [];
      if (this.projetos.some((p) => p.finalizado)) status.push({ valor: 'concluido', rotulo: 'Concluído' });
      if (this.projetos.some((p) => !p.finalizado)) status.push({ valor: 'andamento', rotulo: 'Em andamento' });
      return {
        ano: unicos((p) => p.ano).sort((a, b) => b - a).map((v) => ({ valor: v, rotulo: String(v) })),
        grupo: unicos((p) => p.grupo_insetos).sort(cmp).map((v) => ({ valor: v, rotulo: v })),
        local: unicos((p) => p.local_coleta).sort(cmp).map((v) => ({ valor: v, rotulo: v })),
        status
      };
    },
    filtrosProjetoAtivos() { return Object.values(this.filtros).some((v) => v !== null); },
    indiceProjetos() {
      const mapa = {};
      this.projetos.forEach((p) => {
        const especies = (this.especimesPorProjeto[p.id] || []).map((e) => `${e.especie} ${e.familia || ''}`).join(' ');
        mapa[p.id] = norm([p.titulo, p.grupo_insetos, p.local_coleta, p.ano, p.descricao, p.tracos_medidos, especies].join(' '));
      });
      return mapa;
    },
    rotuloOrdenacao() { return this.opcoesOrdem.find((o) => o.valor === this.ordenacao).rotulo; },
    projetosFiltrados() {
      const f = this.filtros;
      const lista = this.projetos.filter((p) => {
        if (f.ano !== null && p.ano !== f.ano) return false;
        if (f.grupo !== null && p.grupo_insetos !== f.grupo) return false;
        if (f.status !== null && (p.finalizado ? 'concluido' : 'andamento') !== f.status) return false;
        if (f.local !== null && p.local_coleta !== f.local) return false;
        return true;
      });
      if (this.ordenacao === 'titulo') lista.sort((a, b) => cmp(a.titulo, b.titulo));
      else if (this.ordenacao === 'especies') {
        lista.sort((a, b) => this.contarEspecies(this.especimesDe(b)) - this.contarEspecies(this.especimesDe(a)) || cmp(a.titulo, b.titulo));
      } else lista.sort((a, b) => b.ano - a.ano || a.id - b.id);
      return lista;
    },

    // ---------- busca global ----------
    consulta() { return norm(this.termoBusca).trim(); },
    mostrarSug() { return this.sugAberta && this.consulta.length >= 2 && this.rota.nome !== 'busca'; },
    especiesGlobais() {
      const mapa = new Map();
      this.especimes.forEach((e) => {
        if (!mapa.has(e.especie)) mapa.set(e.especie, { nome: e.especie, ordem: e.grupo_insetos, familia: e.familia || '', especimes: [] });
        mapa.get(e.especie).especimes.push(e);
      });
      return [...mapa.values()];
    },
    resultados() {
      const q = this.consulta;
      const vazio = { projetos: [], especies: [], especimes: [], repositorios: [], paginas: [], total: 0 };
      if (q.length < 2) return vazio;
      const r = { ...vazio };
      r.projetos = this.projetos.filter((p) => this.indiceProjetos[p.id].includes(q)).sort((a, b) => b.ano - a.ano || a.id - b.id);
      r.especies = this.especiesGlobais
        .filter((x) => norm(`${x.nome} ${x.familia} ${x.ordem}`).includes(q))
        .sort((a, b) => cmp(a.nome, b.nome));
      r.especimes = this.especimesIndexados
        .filter((i) => norm(`${i.e.codigo_etiqueta} ${i.e.local_coleta || ''}`).includes(q))
        .map((i) => i.e);
      r.repositorios = this.repositorios.filter((x) => norm(`${x.titulo} ${x.descricao || ''}`).includes(q));
      const textoSobre = norm([this.textoSobre, ...this.equipe.map((m) => `${m.nome} ${m.papel}`)].join(' '));
      if (textoSobre.includes(q)) r.paginas = [{ titulo: 'Sobre', trecho: this.textoSobre }];
      r.total = r.projetos.length + r.especies.length + r.especimes.length + r.repositorios.length + r.paginas.length;
      return r;
    },
    sugestoesBusca() {
      const r = this.resultados;
      const lista = [];
      r.projetos.slice(0, 4).forEach((p) => lista.push({ grupo: 'Projetos', rotulo: p.titulo, sub: `${p.grupo_insetos} · ${p.ano}`, href: `#/projetos/${p.id}` }));
      r.especies.slice(0, 4).forEach((x) => lista.push({ grupo: 'Espécies', rotulo: x.nome, italico: true, sub: x.familia || x.ordem, especie: x.nome }));
      r.repositorios.slice(0, 2).forEach((x) => lista.push({ grupo: 'Repositórios', rotulo: x.titulo, sub: 'Zenodo', href: `#/projetos/${x.id}` }));
      r.especimes.slice(0, 3).forEach((e) => lista.push({ grupo: 'Espécimes', rotulo: e.codigo_etiqueta, sub: e.especie, href: this.destinoEspecime(e) }));
      r.paginas.forEach((x) => lista.push({ grupo: 'Páginas', rotulo: x.titulo, sub: '', href: '#/sobre' }));
      return lista;
    },

    // ---------- coleção ----------
    sugestoes() {
      const unicos = (lista) => [...new Set(lista.filter(Boolean))].sort(cmp);
      return {
        grupos: unicos(this.projetos.map((p) => p.grupo_insetos)),
        ordens: unicos(this.especimes.map((e) => e.grupo_insetos)),
        familias: unicos(this.especimes.map((e) => e.familia)),
        tracos: unicos(this.especimes.flatMap((e) => (e.medidas || []).map((m) => m.traco))),
        sexos: ['macho', 'fêmea', 'indeterminado'],
        estagios: ['adulto', 'operária', 'soldado', 'rainha', 'ninfa', 'larva', 'pupa']
      };
    },
    repositorios() {
      return this.projetos
        .filter((p) => ehUrl(p.dataset_externo_url))
        .sort((a, b) => b.ano - a.ano || cmp(a.titulo, b.titulo));
    },
    especimesIndexados() {
      return this.especimes.map((e) => {
        const p = this.projetosPorId[e.projeto_id];
        return { e, texto: norm([e.especie, e.familia, e.grupo_insetos, e.codigo_etiqueta, e.local_coleta, p ? p.titulo : ''].join(' ')) };
      });
    },
    espBase() {
      const q = norm(this.buscaColecao).trim();
      return this.especimesIndexados.filter((i) => !q || i.texto.includes(q)).map((i) => i.e);
    },
    espFiltrados() {
      const f = this.colecaoFiltros;
      return this.espBase.filter((e) => {
        if (f.ordens.length && !f.ordens.includes(e.grupo_insetos)) return false;
        if (f.familias.length && !f.familias.includes(this.familiaDe(e))) return false;
        if (f.repos.length && !f.repos.includes(e.projeto_id)) return false;
        if (f.anos.length) {
          const p = this.projetosPorId[e.projeto_id];
          if (!p || !f.anos.includes(p.ano)) return false;
        }
        return true;
      });
    },
    filtrosColecaoAtivos() {
      const f = this.colecaoFiltros;
      return !!(f.ordens.length || f.familias.length || f.repos.length || f.anos.length);
    },

    facetaOrdens() {
      return [...contarPor(this.espBase, (e) => e.grupo_insetos)]
        .map(([valor, s]) => ({ valor, n: s.size })).sort((a, b) => cmp(a.valor, b.valor));
    },
    facetaFamilias() {
      const o = this.colecaoFiltros.ordens;
      const base = o.length ? this.espBase.filter((e) => o.includes(e.grupo_insetos)) : this.espBase;
      return [...contarPor(base, (e) => this.familiaDe(e))]
        .map(([valor, s]) => ({ valor, n: s.size }))
        .sort((a, b) => (a.valor === SEM_FAMILIA) - (b.valor === SEM_FAMILIA) || cmp(a.valor, b.valor));
    },
    facetaRepos() {
      const contagem = contarPor(this.espBase, (e) => e.projeto_id);
      return this.repositorios.map((r) => ({ valor: r.id, rotulo: r.titulo, n: contagem.has(r.id) ? contagem.get(r.id).size : 0 }));
    },
    facetaAnos() {
      const mapa = new Map();
      this.repositorios.forEach((r) => mapa.set(r.ano, (mapa.get(r.ano) || 0) + 1));
      return [...mapa].map(([valor, n]) => ({ valor, n })).sort((a, b) => b.valor - a.valor);
    },

    arvore() {
      const ordens = new Map();
      this.espFiltrados.forEach((e) => {
        const fam = this.familiaDe(e);
        if (!ordens.has(e.grupo_insetos)) ordens.set(e.grupo_insetos, new Map());
        const familias = ordens.get(e.grupo_insetos);
        if (!familias.has(fam)) familias.set(fam, new Map());
        const especies = familias.get(fam);
        if (!especies.has(e.especie)) especies.set(e.especie, []);
        especies.get(e.especie).push(e);
      });
      return [...ordens].sort(([a], [b]) => cmp(a, b)).map(([nome, familias]) => {
        const lista = [...familias]
          .sort(([a], [b]) => (a === SEM_FAMILIA) - (b === SEM_FAMILIA) || cmp(a, b))
          .map(([fnome, especies]) => ({
            nome: fnome,
            especies: [...especies].sort(([a], [b]) => cmp(a, b)).map(([snome, especimes]) => ({
              nome: snome,
              especimes: especimes.sort((x, y) => cmp(x.codigo_etiqueta, y.codigo_etiqueta)),
              repos: this.reposDe(especimes)
            }))
          }));
        return {
          nome,
          familias: lista,
          nEspecies: lista.reduce((acc, f) => acc + f.especies.length, 0)
        };
      });
    },
    totalEspecies() { return this.arvore.reduce((acc, o) => acc + o.nEspecies, 0); },

    repositoriosFiltrados() {
      const f = this.colecaoFiltros;
      const q = norm(this.buscaColecao).trim();
      const comEspecimes = new Set(this.espFiltrados.map((e) => e.projeto_id));
      const filtraEspecimes = f.ordens.length || f.familias.length;
      return this.repositorios.filter((r) => {
        if (f.anos.length && !f.anos.includes(r.ano)) return false;
        if (!filtraEspecimes && !q) return true;
        if (comEspecimes.has(r.id)) return true;
        return !filtraEspecimes && norm(`${r.titulo} ${r.descricao || ''}`).includes(q);
      });
    },

    // ---------- galeria, mapa e painel ----------
    listaContexto() { return this.rota.nome === 'projeto' ? this.especimesDoProjeto : this.espFiltrados; },
    galeriaVisivel() { return this.listaContexto.slice(0, this.limiteGaleria); },
    galeriaRestante() { return Math.max(this.listaContexto.length - this.limiteGaleria, 0); },
    totalComImagem() { return this.listaContexto.filter((e) => this.urlImagem(e, 100)).length; },
    pontosMapa() {
      return this.listaContexto
        .filter((e) => e.latitude !== null && e.latitude !== undefined && e.longitude !== null && e.longitude !== undefined)
        .map((e) => ({
          id: e.id, lat: e.latitude, lng: e.longitude, cor: this.coresOrdem[e.grupo_insetos] || '#555',
          especie: e.especie, codigo: e.codigo_etiqueta, local: e.local_coleta || '', thumb: this.urlImagem(e, 240)
        }));
    },
    semCoordenadas() { return this.listaContexto.length - this.pontosMapa.length; },
    legendaMapa() {
      const ordens = [...new Set(this.listaContexto.map((e) => e.grupo_insetos))].sort(cmp);
      return ordens.map((o) => ({ nome: o, cor: this.coresOrdem[o] || '#555' }));
    },
    painelEsp() {
      if (!this.painel) return null;
      return this.especimesPorId[this.painel.ids[this.painel.idx]] || null;
    },
    painelProjeto() { return this.painelEsp ? this.projetosPorId[this.painelEsp.projeto_id] || null : null; }
  },

  watch: {
    tituloPagina: { immediate: true, handler(t) { document.title = t; } },
    termoBusca(v) {
      this.idxSug = -1;
      this.sugAberta = true;
      if (this.rota.nome === 'busca') {
        history.replaceState(null, '', v.trim() ? `#/busca/${encodeURIComponent(v.trim())}` : '#/busca');
      }
    },
    buscaColecao() { this.limiteGaleria = POR_PAGINA_GALERIA; this.expandirSeFiltrando(); },
    colecaoFiltros: { deep: true, handler() { this.limiteGaleria = POR_PAGINA_GALERIA; this.expandirSeFiltrando(); } }
  },

  created() {
    this.aplicarRota();
  },

  async mounted() {
    const token = localStorage.getItem('entomobase_token');
    if (tokenValido(token)) {
      this.token = token;
      this.userEmail = localStorage.getItem('entomobase_email');
    } else {
      localStorage.removeItem('entomobase_token');
      localStorage.removeItem('entomobase_email');
    }
    window.addEventListener('hashchange', this.aplicarRota);
    document.addEventListener('click', this.fecharPopups);
    document.addEventListener('keydown', this.aoTecla);
    await this.carregarTudo();
    this.abrirPrimeiro();
  },

  beforeUnmount() {
    window.removeEventListener('hashchange', this.aplicarRota);
    document.removeEventListener('click', this.fecharPopups);
    document.removeEventListener('keydown', this.aoTecla);
  },

  methods: {
    ehUrl,
    fmt,

    // ---------- navegação ----------
    aplicarRota() {
      const [a, b, c] = (location.hash || '').replace(/^#\/?/, '').split('/').filter(Boolean);
      let rota;
      if (a === 'projetos') {
        rota = b ? { nome: 'projeto', id: Number(b), vista: ['galeria', 'mapa'].includes(c) ? c : 'tabela' } : { nome: 'projetos' };
      } else if (a === 'colecao') {
        const visoes = { repositorios: 'repos', mapa: 'mapa' };
        rota = { nome: 'colecao', visao: visoes[b] || 'arvore' };
      } else if (a === 'busca') rota = { nome: 'busca' };
      else rota = { nome: 'sobre' };
      this.rota = rota;
      this.fecharPopups();
      this.limiteGaleria = POR_PAGINA_GALERIA;
      if (rota.nome === 'busca') {
        try { this.termoBusca = decodeURIComponent(b || ''); } catch { this.termoBusca = b || ''; }
      } else {
        this.termoBusca = '';
      }
      if (rota.nome === 'colecao') {
        if (rota.visao === 'repos') this.colecaoFiltros.repos = [];
        else this.colecaoFiltros.anos = [];
      }
      window.scrollTo(0, 0);
    },
    fecharPopups() { this.menuAberto = null; this.popover = null; this.sugAberta = false; },
    aoTecla(ev) {
      const modalAberto = this.confirmacao || this.formEspecime || this.formProjeto || this.importacao || this.info || this.showLogin;
      if (this.painel && !modalAberto) {
        if (ev.key === 'ArrowLeft') { this.navegarPainel(-1); return; }
        if (ev.key === 'ArrowRight') { this.navegarPainel(1); return; }
      }
      if (ev.key !== 'Escape') return;
      this.fecharPopups();
      if (this.confirmacao) this.confirmacao = null;
      else if (this.formEspecime) this.formEspecime = null;
      else if (this.formProjeto) this.formProjeto = null;
      else if (this.importacao) this.importacao = null;
      else if (this.info) this.info = null;
      else if (this.showLogin) this.showLogin = false;
      else if (this.painel) this.painel = null;
    },
    avisar(msg) {
      this.toast = msg;
      clearTimeout(this.timerToast);
      this.timerToast = setTimeout(() => { this.toast = null; }, 4500);
    },

    // ---------- API ----------
    async mensagemErro(res) {
      try {
        const d = (await res.json()).detail;
        if (typeof d === 'string') return d;
        if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join('; ');
      } catch { /* resposta sem corpo JSON */ }
      return `Erro ${res.status}`;
    },
    async api(caminho, { metodo = 'GET', corpo = null } = {}) {
      const headers = {};
      if (corpo !== null) headers['Content-Type'] = 'application/json';
      if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
      let res;
      try {
        res = await fetch(this.apiUrl + caminho, { method: metodo, headers, body: corpo !== null ? JSON.stringify(corpo) : undefined });
      } catch {
        throw new Error('Não foi possível conectar à API.');
      }
      if (res.status === 401 && this.token && caminho !== '/login') {
        this.encerrarSessao();
        this.loginErro = 'Sua sessão expirou. Entre novamente.';
        this.showLogin = true;
        this.formProjeto = this.formEspecime = this.confirmacao = this.importacao = null;
        throw new Error('Sessão expirada.');
      }
      if (!res.ok) throw new Error(await this.mensagemErro(res));
      return res.status === 204 ? null : res.json();
    },
    async carregarTudo() {
      this.carregando = true;
      this.erroApi = null;
      try {
        const [projetos, especimes] = await Promise.all([this.api('/projetos'), this.api('/especimes')]);
        this.projetos = projetos;
        this.especimes = especimes;
      } catch (e) {
        this.erroApi = e.message;
      }
      this.carregando = false;
    },

    // ---------- sessão ----------
    abrirLogin() { this.loginErro = null; this.showLogin = true; },
    async fazerLogin() {
      this.loginErro = null;
      this.enviando = true;
      try {
        const d = await this.api('/login', { metodo: 'POST', corpo: this.credenciais });
        this.token = d.access_token;
        this.userEmail = d.email;
        localStorage.setItem('entomobase_token', this.token);
        localStorage.setItem('entomobase_email', this.userEmail);
        this.showLogin = false;
        this.credenciais = { email: '', senha: '' };
        await this.carregarTudo();
      } catch (e) {
        this.loginErro = e.message;
      }
      this.enviando = false;
    },
    encerrarSessao() {
      this.token = null;
      this.userEmail = null;
      localStorage.removeItem('entomobase_token');
      localStorage.removeItem('entomobase_email');
    },
    async fazerLogout() {
      this.encerrarSessao();
      await this.carregarTudo();
    },

    // ---------- helpers de exibição ----------
    plural(n, um, varios) { return `${n.toLocaleString('pt-BR')} ${n === 1 ? um : varios}`; },
    especimesDe(p) { return this.especimesPorProjeto[p.id] || []; },
    contarEspecies(lista) { return new Set((lista || []).map((e) => e.especie)).size; },
    rotuloStatus(p) { return p.finalizado ? 'Concluído' : 'Em andamento'; },
    corCapa(p) { return PALETA_CAPAS[(p.id - 1 + PALETA_CAPAS.length) % PALETA_CAPAS.length]; },
    estiloCapa(p) {
      const estilo = { backgroundColor: this.corCapa(p) };
      if (ehUrl(p.capa_url)) {
        estilo.backgroundImage = `url("${p.capa_url.trim().replace(/"/g, '%22')}")`;
        estilo.backgroundSize = 'cover';
        estilo.backgroundPosition = 'center';
      }
      return estilo;
    },
    familiaDe(e) { return e.familia || SEM_FAMILIA; },
    formatarData(d) {
      if (!d) return '—';
      const [a, m, dia] = d.split('-');
      return `${dia}/${m}/${a}`;
    },
    valorMedida(e, coluna) {
      const m = (e.medidas || []).find((x) => `${x.traco}|${x.unidade}` === coluna.chave);
      return m ? fmt(m.valor) : '—';
    },
    resumoMedidas(e, n = 3) {
      return (e.medidas || []).slice(0, n).map((m) => ({ traco: m.traco, texto: `${fmt(m.valor)} ${m.unidade}` }));
    },
    corOrdem(o) { return this.coresOrdem[o] || '#555'; },
    reposDe(especimes) {
      const ids = [...new Set(especimes.map((e) => e.projeto_id))];
      return ids
        .map((id) => this.projetosPorId[id])
        .filter((p) => p && ehUrl(p.dataset_externo_url))
        .sort((a, b) => b.ano - a.ano)
        .map((p) => ({ id: p.id, titulo: p.titulo, url: p.dataset_externo_url.trim() }));
    },
    resumoRepositorio(r) {
      const esp = this.especimesDe(r);
      const ordens = [...new Set(esp.map((e) => e.grupo_insetos))].sort(cmp);
      const partes = [this.plural(this.contarEspecies(esp), 'espécie', 'espécies')];
      if (ordens.length) partes.push(ordens.join(', '));
      partes.push(String(r.ano));
      return partes.join(' · ');
    },

    // ---------- imagens (Zenodo) ----------
    registroDe(e) { return Zenodo.idDoRegistro((this.projetosPorId[e.projeto_id] || {}).dataset_externo_url); },
    urlImagem(e, largura = 400) {
      if (ehUrl(e.fotografia_url)) return e.fotografia_url.trim();
      if (!e.imagem_arquivo) return null;
      const id = this.registroDe(e);
      if (!id) return null;
      if (Zenodo.ehDemo(id)) return `${this.apiUrl}/demo/imagem/${encodeURIComponent(e.imagem_arquivo)}`;
      return Zenodo.miniatura(id, e.imagem_arquivo, largura);
    },
    urlArquivo(e) {
      if (!e.imagem_arquivo) return ehUrl(e.fotografia_url) ? e.fotografia_url.trim() : null;
      const id = this.registroDe(e);
      if (!id) return null;
      return Zenodo.ehDemo(id) ? null : Zenodo.arquivo(id, e.imagem_arquivo);
    },
    urlRegistro(e) {
      const p = this.projetosPorId[e.projeto_id];
      return p && ehUrl(p.dataset_externo_url) ? p.dataset_externo_url.trim() : null;
    },

    // ---------- painel de detalhes ----------
    abrirPainel(e, lista) {
      const ids = (lista && lista.length ? lista : [e]).map((x) => x.id);
      this.painel = { ids, idx: Math.max(0, ids.indexOf(e.id)) };
    },
    abrirPainelPorId(id) {
      const e = this.especimesPorId[id];
      if (e) this.abrirPainel(e, this.listaContexto);
    },
    navegarPainel(passo) {
      const n = this.painel.ids.length;
      this.painel.idx = (this.painel.idx + passo + n) % n;
    },
    verNoMapa(e) {
      this.mapaFoco = e.id;
      this.painel = null;
      const alvo = this.rota.nome === 'projeto' ? `#/projetos/${this.rota.id}/mapa` : '#/colecao/mapa';
      if (location.hash === alvo) return;
      location.hash = alvo;
    },
    destinoEspecime(e) { return e.projeto_id ? `#/projetos/${e.projeto_id}` : '#/colecao'; },
    editarDoPainel(e) { this.painel = null; this.abrirFormEspecime(e); },
    excluirDoPainel(e) { this.painel = null; this.pedirExcluirEspecime(e); },

    // ---------- busca global ----------
    moverSug(passo) {
      const n = this.sugestoesBusca.length;
      if (!n) return;
      this.sugAberta = true;
      let i = this.idxSug + passo;
      if (i < 0) i = n - 1;
      if (i >= n) i = 0;
      this.idxSug = i;
    },
    escolherSugestao(s) {
      this.sugAberta = false;
      if (s.especie) this.abrirEspecie(s.especie);
      else location.hash = s.href;
    },
    enviarBusca(forcar = false) {
      if (!forcar && this.idxSug >= 0 && this.sugestoesBusca[this.idxSug]) {
        this.escolherSugestao(this.sugestoesBusca[this.idxSug]);
        return;
      }
      const t = this.termoBusca.trim();
      if (!t) return;
      this.sugAberta = false;
      location.hash = `#/busca/${encodeURIComponent(t)}`;
    },
    abrirEspecie(nome) {
      this.colecaoFiltros = { ordens: [], familias: [], repos: [], anos: [] };
      this.buscaColecao = nome;
      location.hash = '#/colecao';
    },

    // ---------- filtros de projetos ----------
    alternarMenu(chave) { this.popover = null; this.menuAberto = this.menuAberto === chave ? null : chave; },
    definirFiltro(chave, valor) { this.filtros[chave] = valor; this.menuAberto = null; },
    rotuloFiltro(f) {
      const v = this.filtros[f.chave];
      if (v === null) return f.rotulo;
      const op = this.opcoesFiltro[f.chave].find((o) => o.valor === v);
      return `${f.rotulo}: ${op ? op.rotulo : v}`;
    },
    limparFiltrosProjeto() { this.filtros = { ano: null, grupo: null, status: null, local: null }; },

    // ---------- árvore da coleção ----------
    estaAberto(chave) { return !!this.abertos[chave]; },
    alternar(chave) { this.abertos[chave] = !this.abertos[chave]; this.popover = null; },
    alternarPopover(chave) { this.menuAberto = null; this.popover = this.popover === chave ? null : chave; },
    expandirTudo() {
      const abertos = {};
      this.arvore.forEach((o) => {
        abertos[`o:${o.nome}`] = true;
        o.familias.forEach((f) => { abertos[`f:${o.nome}|${f.nome}`] = true; });
      });
      this.abertos = abertos;
    },
    recolherTudo() { this.abertos = {}; },
    abrirPrimeiro() {
      const o = this.arvore[0];
      if (!o || Object.keys(this.abertos).length) return;
      this.abertos[`o:${o.nome}`] = true;
      o.familias.forEach((f) => { this.abertos[`f:${o.nome}|${f.nome}`] = true; });
    },
    expandirSeFiltrando() {
      if (this.buscaColecao.trim() || this.filtrosColecaoAtivos) this.$nextTick(() => this.expandirTudo());
    },
    limparFiltrosColecao() {
      this.colecaoFiltros = { ordens: [], familias: [], repos: [], anos: [] };
      this.buscaColecao = '';
    },

    // ---------- projetos: criar, editar, excluir ----------
    abrirFormProjeto(p = null) {
      this.erroForm = null;
      this.formProjeto = p
        ? {
            id: p.id, titulo: p.titulo, ano: p.ano, grupo_insetos: p.grupo_insetos, tracos_medidos: p.tracos_medidos || '',
            local_coleta: p.local_coleta || '', capa_url: p.capa_url || '', dataset_externo_url: p.dataset_externo_url || '',
            publicacao_vinculada: p.publicacao_vinculada || '', descricao: p.descricao || '', finalizado: !!p.finalizado
          }
        : {
            id: null, titulo: '', ano: new Date().getFullYear(), grupo_insetos: '', tracos_medidos: '', local_coleta: '',
            capa_url: '', dataset_externo_url: '', publicacao_vinculada: '', descricao: '', finalizado: false
          };
    },
    async salvarProjeto() {
      const f = this.formProjeto;
      this.erroForm = null;
      this.enviando = true;
      const corpo = {
        titulo: f.titulo.trim(), ano: Number(f.ano), grupo_insetos: f.grupo_insetos.trim(),
        tracos_medidos: nulo(f.tracos_medidos), local_coleta: nulo(f.local_coleta), capa_url: nulo(f.capa_url),
        dataset_externo_url: nulo(f.dataset_externo_url), publicacao_vinculada: nulo(f.publicacao_vinculada),
        descricao: nulo(f.descricao), finalizado: !!f.finalizado
      };
      try {
        const salvo = await this.api(f.id ? `/projetos/${f.id}` : '/projetos', { metodo: f.id ? 'PUT' : 'POST', corpo });
        this.formProjeto = null;
        await this.carregarTudo();
        this.avisar(f.id ? 'Projeto atualizado.' : 'Projeto criado.');
        if (!f.id) location.hash = `#/projetos/${salvo.id}`;
      } catch (e) {
        this.erroForm = e.message;
      }
      this.enviando = false;
    },
    pedirExcluirProjeto(p) {
      this.erroForm = null;
      const n = this.especimesDe(p).length;
      this.confirmacao = {
        titulo: 'Excluir projeto',
        texto: `"${p.titulo}" será excluído${n ? ` junto com ${this.plural(n, 'espécime', 'espécimes')}` : ''}. Essa ação não pode ser desfeita.`,
        acao: async () => {
          await this.api(`/projetos/${p.id}`, { metodo: 'DELETE' });
          location.hash = '#/projetos';
          await this.carregarTudo();
          this.avisar('Projeto excluído.');
        }
      };
    },

    // ---------- espécimes: criar, editar, excluir ----------
    abrirFormEspecime(e = null, projetoId = null) {
      this.erroForm = null;
      if (e) {
        this.formEspecime = {
          id: e.id, codigo_etiqueta: e.codigo_etiqueta, grupo_insetos: e.grupo_insetos, familia: e.familia || '',
          especie: e.especie, data_coleta: e.data_coleta || '', local_coleta: e.local_coleta || '',
          latitude: e.latitude ?? '', longitude: e.longitude ?? '', altitude_m: e.altitude_m ?? '',
          sexo: e.sexo || '', estagio: e.estagio || '', imagem_arquivo: e.imagem_arquivo || '', fotografia_url: e.fotografia_url || '',
          notas: e.notas || '', projeto_id: e.projeto_id ?? null,
          medidas: (e.medidas || []).map((m) => ({ traco: m.traco, valor: m.valor, unidade: m.unidade }))
        };
      } else {
        const projeto = this.projetosPorId[projetoId];
        const tracos = projeto && projeto.tracos_medidos ? projeto.tracos_medidos.split(',').map((t) => t.trim()).filter(Boolean) : [];
        this.formEspecime = {
          id: null, codigo_etiqueta: '', grupo_insetos: '', familia: '', especie: '', data_coleta: '', local_coleta: projeto ? projeto.local_coleta || '' : '',
          latitude: '', longitude: '', altitude_m: '', sexo: '', estagio: '', imagem_arquivo: '', fotografia_url: '',
          notas: '', projeto_id: projetoId,
          medidas: tracos.map((t) => ({ traco: t, valor: '', unidade: 'mm' }))
        };
      }
    },
    adicionarMedida() { this.formEspecime.medidas.push({ traco: '', valor: '', unidade: 'mm' }); },
    removerMedida(i) { this.formEspecime.medidas.splice(i, 1); },
    async salvarEspecime() {
      const f = this.formEspecime;
      this.erroForm = null;
      const medidas = [];
      for (const m of f.medidas) {
        const valor = num(m.valor);
        const traco = (m.traco || '').trim();
        if (valor === null && !traco) continue;
        if (valor === null) continue;
        if (!traco) { this.erroForm = 'Dê um nome ao traço de cada medida preenchida.'; return; }
        medidas.push({ traco, valor, unidade: (m.unidade || 'mm').trim() || 'mm' });
      }
      const corpo = {
        codigo_etiqueta: f.codigo_etiqueta.trim(), grupo_insetos: f.grupo_insetos.trim(), familia: nulo(f.familia),
        especie: f.especie.trim(), data_coleta: nulo(f.data_coleta), local_coleta: nulo(f.local_coleta),
        latitude: num(f.latitude), longitude: num(f.longitude), altitude_m: num(f.altitude_m),
        sexo: nulo(f.sexo), estagio: nulo(f.estagio), imagem_arquivo: nulo(f.imagem_arquivo), fotografia_url: nulo(f.fotografia_url),
        notas: nulo(f.notas), projeto_id: f.projeto_id || null, medidas
      };
      this.enviando = true;
      try {
        await this.api(f.id ? `/especimes/${f.id}` : '/especimes', { metodo: f.id ? 'PUT' : 'POST', corpo });
        this.formEspecime = null;
        await this.carregarTudo();
        this.avisar(f.id ? 'Espécime atualizado.' : 'Espécime adicionado.');
      } catch (e) {
        this.erroForm = e.message;
      }
      this.enviando = false;
    },
    pedirExcluirEspecime(e) {
      this.erroForm = null;
      this.confirmacao = {
        titulo: 'Excluir espécime',
        texto: `O espécime ${e.codigo_etiqueta} (${e.especie}) será excluído. Essa ação não pode ser desfeita.`,
        acao: async () => {
          await this.api(`/especimes/${e.id}`, { metodo: 'DELETE' });
          await this.carregarTudo();
          this.avisar('Espécime excluído.');
        }
      };
    },
    async executarConfirmacao() {
      this.enviando = true;
      this.erroForm = null;
      try {
        await this.confirmacao.acao();
        this.confirmacao = null;
      } catch (e) {
        if (this.confirmacao) this.erroForm = e.message;
      }
      this.enviando = false;
    },

    // ---------- importação de CSV ----------
    textoErro(msg) {
      return String(msg)
        .replace(/grupo_insetos/g, 'Ordem').replace(/codigo_etiqueta/g, 'Código da etiqueta').replace(/especie/g, 'Espécie')
        .replace(/Field required/g, 'campo obrigatório')
        .replace(/Input should be less than or equal to (-?[\d.]+)/g, 'deve ser no máximo $1')
        .replace(/Input should be greater than or equal to (-?[\d.]+)/g, 'deve ser no mínimo $1')
        .replace(/Input should be a valid (number|date)[^;]*/g, 'valor inválido').replace(/String should have at least 1 character/g, 'não pode ficar vazio');
    },
    abrirImportacao(projetoId = null) {
      const p = this.projetosPorId[projetoId];
      this.importacao = {
        projetoFixo: projetoId !== null, projetoId, nomeProjeto: p ? p.titulo : '',
        nomeArquivo: '', cabecalhos: [], mapa: [], dados: [], duplicados: 'ignorar',
        padrao: { grupo_insetos: '', familia: '', especie: '' },
        errosCliente: [], linhasPayload: [], relatorio: null, simulando: false, erro: null, seq: 0
      };
    },
    async lerArquivoImportacao(ev) {
      const arquivo = ev.target.files && ev.target.files[0];
      if (!arquivo) return;
      const im = this.importacao;
      im.erro = null;
      try {
        const linhas = lerCsv(await arquivo.text());
        if (linhas.length < 2) throw new Error('O arquivo precisa ter uma linha de cabeçalho e pelo menos uma linha de dados.');
        if (linhas.length - 1 > 5000) throw new Error('O arquivo tem mais de 5.000 linhas. Divida em partes menores.');
        im.nomeArquivo = arquivo.name;
        im.cabecalhos = linhas[0].map((h) => h.trim());
        im.mapa = im.cabecalhos.map((h) => interpretarCabecalho(h));
        im.dados = linhas.slice(1);
        await this.simularImportacao();
      } catch (e) {
        im.erro = e.message;
      }
      ev.target.value = '';
    },
    montarLinhasImportacao() {
      const im = this.importacao;
      const linhas = [];
      const erros = [];
      im.dados.forEach((cels, k) => {
        const n = k + 2;
        const o = { linha: n };
        const falhas = [];
        im.mapa.forEach((col, i) => {
          const bruto = (cels[i] ?? '').trim();
          if (bruto === '' || col.destino === 'ignorar') return;
          if (col.destino === 'medida') {
            const valor = numeroBr(bruto);
            if (Number.isNaN(valor)) { falhas.push(`valor inválido em "${col.traco}": ${bruto}`); return; }
            (o.medidas = o.medidas || []).push({ traco: col.traco, valor, unidade: col.unidade || 'mm' });
            return;
          }
          const campo = col.destino.slice(6);
          if (['latitude', 'longitude', 'altitude_m'].includes(campo)) {
            const v = numeroBr(bruto);
            if (Number.isNaN(v)) falhas.push(`${campo}: valor inválido (${bruto})`); else o[campo] = v;
          } else if (campo === 'data_coleta') o[campo] = dataIso(bruto);
          else if (campo === 'projeto') {
            const p = this.projetos.find((x) => norm(x.titulo) === norm(bruto));
            if (p) o.projeto_id = p.id; else falhas.push(`projeto "${bruto}" não encontrado`);
          } else if (campo === 'projeto_id') {
            const v = numeroBr(bruto);
            if (Number.isNaN(v)) falhas.push(`projeto_id inválido (${bruto})`); else o.projeto_id = v;
          } else o[campo] = bruto;
        });
        ['grupo_insetos', 'familia', 'especie'].forEach((c) => {
          if (!o[c] && im.padrao[c].trim()) o[c] = im.padrao[c].trim();
        });
        if (falhas.length) erros.push({ linha: n, codigo_etiqueta: o.codigo_etiqueta || '', mensagem: falhas.join('; ') });
        else linhas.push(o);
      });
      return { linhas, erros };
    },
    agendarSimulacao() {
      clearTimeout(this.timerSimulacao);
      this.timerSimulacao = setTimeout(() => this.simularImportacao(), 350);
    },
    async simularImportacao() {
      const im = this.importacao;
      if (!im || !im.dados.length) return;
      const seq = ++im.seq;
      const { linhas, erros } = this.montarLinhasImportacao();
      im.errosCliente = erros;
      im.linhasPayload = linhas;
      im.erro = null;
      if (!linhas.length) { im.relatorio = null; return; }
      im.simulando = true;
      try {
        const rel = await this.api('/especimes/importar?simular=true', {
          metodo: 'POST', corpo: { projeto_id: im.projetoId || null, duplicados: im.duplicados, linhas }
        });
        if (seq === im.seq) im.relatorio = rel;
      } catch (e) {
        if (seq === im.seq) { im.relatorio = null; im.erro = e.message; }
      }
      if (seq === im.seq) im.simulando = false;
    },
    async confirmarImportacao() {
      const im = this.importacao;
      im.enviando = true;
      im.erro = null;
      try {
        const rel = await this.api('/especimes/importar', {
          metodo: 'POST', corpo: { projeto_id: im.projetoId || null, duplicados: im.duplicados, linhas: im.linhasPayload }
        });
        this.importacao = null;
        await this.carregarTudo();
        const partes = [];
        if (rel.criados) partes.push(this.plural(rel.criados, 'espécime criado', 'espécimes criados'));
        if (rel.atualizados) partes.push(this.plural(rel.atualizados, 'atualizado', 'atualizados'));
        if (rel.ignorados) partes.push(this.plural(rel.ignorados, 'ignorado', 'ignorados'));
        this.avisar(`Importação concluída: ${partes.join(', ') || 'nada novo'}.`);
      } catch (e) {
        im.erro = e.message;
        im.enviando = false;
      }
    },
    baixarModelo() {
      const im = this.importacao;
      const p = this.projetosPorId[im.projetoId];
      const tracos = p && p.tracos_medidos ? p.tracos_medidos.split(',').map((t) => `${t.trim()} (mm)`) : ['Comprimento corporal (mm)'];
      const cab = ['Codigo Etiqueta', 'Ordem', 'Familia', 'Especie', 'Data Coleta', 'Local Coleta', 'Latitude', 'Longitude', 'Altitude (m)', 'Sexo', 'Estagio', 'Imagem', 'Notas', ...tracos];
      const exemplo = ['EX-0001', 'Coleoptera', 'Coccinellidae', 'Coccinella septempunctata', '2025-03-14', 'Parque Estadual do Rio Doce', '-19.75', '-42.60', '250', 'fêmea', 'adulto', 'EX-0001.jpg', '', ...tracos.map(() => '6.5')];
      this.baixarTexto('﻿' + [cab, exemplo].map((l) => l.join(',')).join('\n'), 'modelo_importacao_entomobase.csv');
    },
    baixarTexto(texto, nome) {
      const url = URL.createObjectURL(new Blob([texto], { type: 'text/csv;charset=utf-8' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = nome;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },

    // ---------- exportação e rodapé ----------
    async exportarCsv(projetoId = null) {
      try {
        const q = projetoId ? `?projeto_id=${projetoId}` : '';
        const res = await fetch(`${this.apiUrl}/exportar/csv${q}`, { headers: this.token ? { Authorization: `Bearer ${this.token}` } : {} });
        if (!res.ok) throw new Error(await this.mensagemErro(res));
        const url = URL.createObjectURL(await res.blob());
        const a = document.createElement('a');
        a.href = url;
        a.download = projetoId ? `projeto_${projetoId}_especimes.csv` : 'acervo_entomobase.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        this.avisar(e.message === 'Failed to fetch' ? 'Não foi possível conectar à API.' : e.message);
      }
    },
    abrirInfo(qual) { this.info = qual; },
    async copiarCitacao() {
      try {
        await navigator.clipboard.writeText(this.textoCitacao);
        this.avisar('Citação copiada.');
      } catch {
        this.avisar('Não foi possível copiar. Selecione o texto e copie manualmente.');
      }
    }
  }
});

// ------------------------------------------------------------ componentes
app.directive('foco', { mounted(el) { el.focus(); } });

app.component('icone', {
  props: ['nome'],
  computed: { caminho() { return ICONES[this.nome] || ''; } },
  template: '<svg class="icone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" v-html="caminho"></svg>'
});

app.component('destaque', {
  props: ['texto', 'q'],
  computed: {
    partes() {
      const t = (this.texto ?? '').toString();
      const n = norm(t);
      if (!this.q || n.length !== t.length) return [{ t, m: false }];
      const partes = [];
      let i = 0;
      let j;
      while ((j = n.indexOf(this.q, i)) !== -1) {
        if (j > i) partes.push({ t: t.slice(i, j), m: false });
        partes.push({ t: t.slice(j, j + this.q.length), m: true });
        i = j + this.q.length;
      }
      if (i < t.length) partes.push({ t: t.slice(i), m: false });
      return partes.length ? partes : [{ t, m: false }];
    }
  },
  template: '<span><template v-for="(p, i) in partes" :key="i"><mark v-if="p.m">{{ p.t }}</mark><template v-else>{{ p.t }}</template></template></span>'
});

// imagem com quadro de reserva quando o arquivo não existe ou não carrega
app.component('foto', {
  props: ['src', 'alt', 'rotulo'],
  data() { return { erro: false }; },
  watch: { src() { this.erro = false; } },
  template: '<div :class="[\'foto-quadro\', { vazia: !src || erro }]"><img v-if="src && !erro" :src="src" :alt="alt" loading="lazy" decoding="async" @error="erro = true"><span v-else class="foto-ausente">{{ rotulo || \'Sem imagem\' }}</span></div>'
});

app.component('galeria', {
  props: ['itens', 'restante'],
  emits: ['abrir', 'mais'],
  template: '#tpl-galeria'
});

// mapa de coleta (Leaflet + agrupamento de pontos)
app.component('mapa', {
  props: ['pontos', 'foco'],
  emits: ['abrir', 'focado'],
  data() { return { indisponivel: false, mapaLeaflet: null, grupo: null, marcadores: {} }; },
  template: '<div class="mapa-caixa"><div ref="el" class="mapa" role="application" aria-label="Mapa de coleta"></div><p v-if="indisponivel" class="mapa-erro">Não foi possível carregar o mapa (biblioteca Leaflet indisponível). Verifique a conexão com a internet.</p></div>',
  mounted() {
    if (typeof L === 'undefined' || !L.markerClusterGroup) { this.indisponivel = true; return; }
    const mapa = L.map(this.$refs.el, { scrollWheelZoom: false, worldCopyJump: true }).setView([-15, -47], 4);
    // tiles da Esri: sem chave de API e sem exigir Referer (o OpenStreetMap e o CARTO bloqueiam nesses casos)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19, attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors'
    }).addTo(mapa);
    mapa.on('click', () => mapa.scrollWheelZoom.enable());
    mapa.getContainer().addEventListener('mouseleave', () => mapa.scrollWheelZoom.disable());
    this.mapaLeaflet = markRaw(mapa);
    this.desenhar(true);
    this.$nextTick(() => { mapa.invalidateSize(); this.focar(); });
  },
  beforeUnmount() { if (this.mapaLeaflet) this.mapaLeaflet.remove(); },
  watch: {
    pontos() { this.desenhar(true); },
    foco() { this.focar(); }
  },
  methods: {
    popup(p) {
      const no = document.createElement('div');
      no.className = 'pop';
      if (p.thumb) {
        const img = document.createElement('img');
        img.src = p.thumb;
        img.alt = p.especie;
        img.onerror = () => img.remove();
        no.appendChild(img);
      }
      const nome = document.createElement('strong');
      nome.className = 'pop-especie';
      nome.textContent = p.especie;
      const cod = document.createElement('span');
      cod.className = 'pop-linha';
      cod.textContent = p.codigo + (p.local ? ' · ' + p.local : '');
      const botao = document.createElement('button');
      botao.type = 'button';
      botao.className = 'pop-botao';
      botao.textContent = 'Ver detalhes';
      botao.addEventListener('click', () => this.$emit('abrir', p.id));
      no.append(nome, cod, botao);
      return no;
    },
    desenhar(ajustar) {
      if (!this.mapaLeaflet) return;
      if (this.grupo) this.mapaLeaflet.removeLayer(this.grupo);
      const grupo = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 42 });
      const marcadores = {};
      (this.pontos || []).forEach((p) => {
        const icone = L.divIcon({ className: 'ponto-wrap', html: `<span class="ponto" style="background:${p.cor}"></span>`, iconSize: [18, 18], iconAnchor: [9, 9], popupAnchor: [0, -10] });
        const m = L.marker([p.lat, p.lng], { icon: icone, title: `${p.especie} (${p.codigo})` });
        m.bindPopup(() => this.popup(p), { minWidth: 190, maxWidth: 240 });
        marcadores[p.id] = m;
        grupo.addLayer(m);
      });
      this.mapaLeaflet.addLayer(grupo);
      this.grupo = markRaw(grupo);
      this.marcadores = markRaw(marcadores);
      if (ajustar) {
        if ((this.pontos || []).length) this.mapaLeaflet.fitBounds(grupo.getBounds().pad(0.15), { maxZoom: 13 });
        else this.mapaLeaflet.setView([-15, -47], 4);
      }
      this.focar();
    },
    focar() {
      if (!this.mapaLeaflet || !this.foco) return;
      const m = this.marcadores[this.foco];
      if (!m) return;
      this.grupo.zoomToShowLayer(m, () => m.openPopup());
      this.$emit('focado');
    }
  }
});

app.mount('#app');