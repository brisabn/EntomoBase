const { createApp, markRaw } = Vue;

// every text shown to users comes from i18n.js (Portuguese and English); everything else is in English

const COVER_PALETTE = ['#c9d9a2', '#e9b78a', '#e3b9a3', '#b8cfc0'];
const ORDER_COLORS = ['#c8762b', '#4f7a3a', '#8a4f7d', '#2f6f8f', '#b04a3a', '#7a6a2a'];
const GALLERY_PAGE_SIZE = 48;
const LANGUAGES = ['pt', 'en'];
const LOCALES = { pt: 'pt-BR', en: 'en-US' };

// words used in the address bar for each language: #/projetos/1/galeria and #/en/projects/1/gallery
const ROUTE_WORDS = {
  pt: { about: 'sobre', projects: 'projetos', collection: 'colecao', search: 'busca', gallery: 'galeria', map: 'mapa', repos: 'repositorios' },
  en: { about: 'about', projects: 'projects', collection: 'collection', search: 'search', gallery: 'gallery', map: 'map', repos: 'repositories' }
};
// table sort keys as they appear in the address bar (?o=especie / ?o=species); measurement columns keep their "m:" key
const SORT_WORDS = {
  pt: { catalog: 'codigo', species: 'especie', family: 'familia', locality: 'local', date: 'data' },
  en: { catalog: 'catalog', species: 'species', family: 'family', locality: 'locality', date: 'date' }
};

// the internal key for a word of the address bar, accepting the words of both languages
function wordKey(table, word) {
  for (const lang of LANGUAGES) {
    const found = Object.entries(table[lang]).find(([, w]) => w === word);
    if (found) return found[0];
  }
  return null;
}

const ICONS = {
  external: '<path d="M7 17 17 7M8.5 7H17v8.5"/>',
  back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
  left: '<path d="m15 5-7 7 7 7"/>',
  right: '<path d="m9 5 7 7-7 7"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>'
};

const norm = (s) => (s ?? '').toString().normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const isUrl = (s) => /^https?:\/\//i.test((s || '').trim());
const orNull = (s) => ((s ?? '').toString().trim() || null);
const num = (v) => (v === '' || v === null || v === undefined || Number.isNaN(v) ? null : Number(v));
const cmp = (a, b) => a.localeCompare(b, 'pt-BR');
// internal key for specimens without a family; shown with the "no family" text of the language
const NO_FAMILY = '';
// fields whose values come from a fixed vocabulary (see VOCABULARY in i18n.js)
const VOCABULARY_FIELDS = ['sex', 'life_stage', 'loan_status', 'sampling_method'];

function tokenIsValid(token) {
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return !payload.exp || payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

function countBy(list, keyFn) {
  const map = new Map();
  list.forEach((e) => {
    const k = keyFn(e);
    if (!map.has(k)) map.set(k, new Set());
    map.get(k).add(e.species);
  });
  return map;
}

// reads the saved language choice; browser storage can be unavailable
function savedLanguage() {
  try { return localStorage.getItem('entomobase_lang'); } catch { return null; }
}

// ------------------------------------------------------------------ CSV
function parseCsv(text) {
  text = text.replace(/^﻿/, '');
  const first = text.split(/\r?\n/, 1)[0] || '';
  const delimiter = [';', '\t', ','].map((d) => [d, first.split(d).length]).sort((a, b) => b[1] - a[1])[0][0];
  const rows = [];
  let cell = '';
  let row = [];
  let quoted = false;
  const endRow = () => {
    row.push(cell);
    cell = '';
    if (row.some((x) => x.trim() !== '')) rows.push(row);
    row = [];
  };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { cell += '"'; i++; } else quoted = false;
      } else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === delimiter) { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; endRow(); }
    else cell += c;
  }
  if (cell !== '' || row.length) endRow();
  return rows;
}

// header names accepted in imported files, in Portuguese and English
const ALIASES = {
  catalog_number: ['codigo_etiqueta', 'codigo', 'etiqueta', 'cod', 'id_etiqueta', 'tombo', 'catalog_number'],
  insect_order: ['ordem', 'grupo', 'grupo_insetos', 'order', 'insect_order'],
  family: ['familia', 'family'],
  species: ['especie', 'species', 'nome_cientifico'],
  collection_date: ['data_coleta', 'data', 'data_da_coleta', 'date', 'collection_date'],
  locality: ['local_coleta', 'local', 'localidade', 'locality'],
  latitude: ['latitude', 'lat'],
  longitude: ['longitude', 'lon', 'lng', 'long'],
  elevation_m: ['altitude', 'altitude_m', 'alt', 'elevation', 'elevation_m'],
  sex: ['sexo', 'sex'],
  life_stage: ['estagio', 'estadio', 'casta', 'life_stage'],
  image_file: ['imagem', 'imagem_arquivo', 'arquivo_imagem', 'arquivo', 'foto', 'imagem_zenodo', 'image', 'image_file'],
  photo_url: ['fotografia_url', 'url_imagem', 'foto_url', 'photo_url'],
  notes: ['notas', 'observacoes', 'obs', 'observacao', 'notes'],
  identified_by: ['determinador', 'identificado_por', 'identificador', 'identified_by'],
  identification_date: ['data_determinacao', 'data_da_determinacao', 'data_identificacao', 'identification_date'],
  sampling_method: ['metodo_coleta', 'metodo', 'metodo_de_coleta', 'sampling_method'],
  habitat: ['habitat'],
  collector: ['coletor', 'coletado_por', 'coletores', 'collector'],
  field_number: ['numero_campo', 'numero_de_campo', 'n_campo', 'field_number'],
  storage_location: ['localizacao_fisica', 'localizacao', 'caixa', 'gaveta', 'storage_location'],
  loan_status: ['emprestimo', 'emprestimo_situacao', 'situacao_emprestimo', 'loan_status'],
  loaned_to: ['emprestado_para', 'emprestimo_para', 'loaned_to'],
  loan_date: ['data_emprestimo', 'emprestimo_data', 'loan_date'],
  internal_notes: ['notas_internas', 'observacoes_internas', 'internal_notes'],
  project: ['projeto', 'titulo_projeto', 'project'],
  project_id: ['projeto_id', 'id_projeto', 'project_id']
};
// order of the fields in the column target menu; labels are importField.* in i18n.js
const IMPORT_FIELDS = [
  'catalog_number', 'insect_order', 'family', 'species', 'collection_date', 'locality', 'latitude', 'longitude',
  'elevation_m', 'sex', 'life_stage', 'image_file', 'photo_url', 'notes', 'project', 'project_id',
  'identified_by', 'identification_date', 'sampling_method', 'habitat', 'collector', 'field_number', 'storage_location',
  'loan_status', 'loaned_to', 'loan_date', 'internal_notes'
];

function headerKey(h) {
  return norm(h.replace(/\([^)]*\)/g, '')).replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function interpretHeader(h) {
  const key = headerKey(h);
  for (const [field, names] of Object.entries(ALIASES)) {
    if (names.includes(key)) return { target: `field:${field}`, trait: '', unit: 'mm' };
  }
  if (key === 'id') return { target: 'ignore', trait: '', unit: 'mm' };
  const m = /\(([^)]*)\)\s*$/.exec(h);
  return { target: 'measurement', trait: h.replace(/\([^)]*\)\s*$/, '').trim(), unit: m && m[1].trim() ? m[1].trim() : 'mm' };
}

// accepts the Brazilian decimal comma
function parseNumber(v) {
  const t = String(v).trim().replace(/\s/g, '').replace(',', '.');
  return t !== '' && Number.isFinite(Number(t)) ? Number(t) : NaN;
}

function toIsoDate(v) {
  const t = String(v).trim();
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(t);
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  m = /^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/.exec(t);
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  return t;
}

// ------------------------------------------------------------------ Zenodo
// all URL building rules live here, so they are easy to adjust if Zenodo changes
const Zenodo = {
  recordId(url) {
    const t = url || '';
    const m = /zenodo\.org\/records?\/(\d+)/i.exec(t) || /10\.5281\/zenodo\.(\d+)/i.exec(t);
    return m ? m[1] : null;
  },
  // ids starting with 0 are fake (Zenodo never uses them); their images come from the API /demo route
  isDemo(id) { return !!id && id.startsWith('0'); },
  thumbnail(id, file, width) {
    return `https://zenodo.org/api/iiif/record:${id}:${encodeURIComponent(file)}/full/${width},/0/default.jpg`;
  },
  file(id, file) {
    return `https://zenodo.org/records/${id}/files/${encodeURIComponent(file)}`;
  }
};

const app = createApp({
  data() {
    return {
      apiUrl: ((window.ENTOMOBASE_CONFIG || {}).apiUrl || 'http://127.0.0.1:8000').replace(/\/+$/, ''),
      lang: 'pt',
      route: { name: 'about' },
      searchTerm: '',
      collectionSearch: '',
      suggestionsOpen: false,
      suggestionIndex: -1,
      sortOrder: 'recent',
      sortKeys: ['recent', 'title', 'species'],
      loading: true,
      apiError: null,
      projects: [],
      specimens: [],
      token: null,
      userEmail: null,
      showLogin: false,
      loginError: null,
      credentials: { email: '', password: '' },
      submitting: false,
      openMenu: null,
      popover: null,
      filters: { year: null, group: null, status: null, locality: null },
      collectionFilters: { orders: [], families: [], repos: [], years: [] },
      familiesOpen: false,
      mobileFiltersOpen: false,
      expanded: {},
      galleryLimit: GALLERY_PAGE_SIZE,
      panel: null,
      mapFocus: null,
      projectForm: null,
      specimenForm: null,
      importJob: null,
      formError: null,
      nameHint: null,
      table: { page: 1, perPage: 25, sort: 'catalog', dir: 'asc', query: '' },
      pageSizes: [25, 50, 100],
      confirmation: null,
      info: null,
      toast: null,
      projectFilterKeys: ['year', 'group', 'status', 'locality'],
      importFields: IMPORT_FIELDS,
      teamSize: 3
    };
  },

  computed: {
    locale() { return LOCALES[this.lang]; },
    labAccess() { return !!this.token; },
    activeTab() { return this.route.name === 'project' ? 'projects' : this.route.name; },
    collectionView() { return this.route.view || 'tree'; },
    projectView() { return this.route.view || 'table'; },
    tabs() {
      return ['about', 'projects', 'collection'].map((id) => ({ id, label: this.t(`tab.${id}`), href: this.link(id) }));
    },
    sortOptions() { return this.sortKeys.map((value) => ({ value, label: this.t(`sort.${value}`) })); },
    projectFilters() { return this.projectFilterKeys.map((key) => ({ key, label: this.t(`filter.${key}`) })); },
    aboutText() { return this.t('about.text'); },
    contact() { return this.t('contact.value'); },
    team() {
      return Array.from({ length: this.teamSize }, () => ({ initials: 'NS', name: this.t('about.team_name'), role: this.t('about.team_role') }));
    },
    contactIsEmail() { return /^[^\s@\[\]]+@[^\s@\[\]]+\.[^\s@\[\]]+$/.test(this.contact); },

    citationText() {
      const date = new Date().toLocaleDateString(this.locale, { day: 'numeric', month: 'long', year: 'numeric' });
      return this.t('cite.text', { url: location.href.split('#')[0], date });
    },

    pageTitle() {
      const names = { about: 'tab.about', projects: 'tab.projects', collection: 'tab.collection', search: 'title.search' };
      if (this.route.name === 'project') {
        return this.currentProject ? `${this.currentProject.title} · EntomoBase` : `${this.t('title.project')} · EntomoBase`;
      }
      return `${this.t(names[this.route.name])} · EntomoBase`;
    },

    // ---------- base data ----------
    projectsById() {
      const map = {};
      this.projects.forEach((p) => { map[p.id] = p; });
      return map;
    },
    specimensById() {
      const map = {};
      this.specimens.forEach((e) => { map[e.id] = e; });
      return map;
    },
    specimensByProject() {
      const map = {};
      this.specimens.forEach((e) => {
        if (e.project_id === null || e.project_id === undefined) return;
        (map[e.project_id] = map[e.project_id] || []).push(e);
      });
      return map;
    },
    orderColors() {
      const orders = [...new Set(this.specimens.map((e) => e.insect_order))].sort(cmp);
      const map = {};
      orders.forEach((o, i) => { map[o] = ORDER_COLORS[i % ORDER_COLORS.length]; });
      return map;
    },

    // ---------- projects ----------
    currentProject() {
      return this.route.name === 'project' ? (this.projectsById[this.route.id] || null) : null;
    },
    sortedTable() {
      const q = norm(this.table.query).trim();
      let list = this.projectSpecimens;
      if (q) {
        list = list.filter((e) => norm([e.catalog_number, e.species, e.family, e.locality, e.identified_by, e.sex, e.life_stage,
          this.vocab('sex', e.sex), this.vocab('life_stage', e.life_stage)].join(' ')).includes(q));
      }
      const { sort, dir } = this.table;
      const value = (e) => {
        if (sort === 'species') return e.species;
        if (sort === 'family') return e.family;
        if (sort === 'locality') return e.locality;
        if (sort === 'date') return e.collection_date;
        if (sort.startsWith('m:')) {
          const m = (e.measurements || []).find((x) => `${x.trait}|${x.unit}` === sort.slice(2));
          return m ? m.value : null;
        }
        return e.catalog_number;
      };
      const empty = (v) => v === null || v === undefined || v === '';
      const sign = dir === 'desc' ? -1 : 1;
      return [...list].sort((a, b) => {
        const x = value(a);
        const y = value(b);
        if (empty(x)) return empty(y) ? 0 : 1;
        if (empty(y)) return -1;
        const r = typeof x === 'number' && typeof y === 'number' ? x - y : cmp(String(x), String(y));
        return r * sign || cmp(a.catalog_number, b.catalog_number);
      });
    },
    totalPages() { return Math.max(1, Math.ceil(this.sortedTable.length / this.table.perPage)); },
    currentPage() { return Math.min(Math.max(1, this.table.page), this.totalPages); },
    tablePage() {
      const start = (this.currentPage - 1) * this.table.perPage;
      return this.sortedTable.slice(start, start + this.table.perPage);
    },
    tableRange() {
      const n = this.sortedTable.length;
      if (!n) return this.t('table.range_empty');
      const start = (this.currentPage - 1) * this.table.perPage + 1;
      return this.t('table.range', { start, end: Math.min(n, start + this.table.perPage - 1), total: this.n(n) });
    },
    pageButtons() {
      const total = this.totalPages;
      const current = this.currentPage;
      const nums = new Set([1, total, current - 1, current, current + 1]);
      if (current <= 3) { nums.add(2); nums.add(3); nums.add(4); }
      if (current >= total - 2) { nums.add(total - 1); nums.add(total - 2); nums.add(total - 3); }
      const list = [...nums].filter((n) => n >= 1 && n <= total).sort((x, y) => x - y);
      const out = [];
      list.forEach((n, i) => {
        if (i && n - list[i - 1] > 1) out.push({ ellipsis: true, key: `r${n}` });
        out.push({ n, key: `p${n}` });
      });
      return out;
    },
    projectTraits() {
      const p = this.currentProject;
      return p && p.measured_traits ? p.measured_traits.split(',').map((t) => t.trim()).filter(Boolean) : [];
    },
    projectSpecimens() {
      const p = this.currentProject;
      if (!p) return [];
      return [...(this.specimensByProject[p.id] || [])].sort((a, b) => cmp(a.catalog_number, b.catalog_number));
    },
    measurementColumns() {
      const columns = [];
      this.projectSpecimens.forEach((e) => (e.measurements || []).forEach((m) => {
        const key = `${m.trait}|${m.unit}`;
        if (!columns.some((c) => c.key === key)) columns.push({ key, trait: m.trait, unit: m.unit });
      }));
      return columns;
    },
    filterOptions() {
      const unique = (fn) => [...new Set(this.projects.map(fn).filter((v) => v !== null && v !== undefined && v !== ''))];
      const status = [];
      if (this.projects.some((p) => p.finished)) status.push({ value: 'finished', label: this.t('status.finished') });
      if (this.projects.some((p) => !p.finished)) status.push({ value: 'in_progress', label: this.t('status.in_progress') });
      return {
        year: unique((p) => p.year).sort((a, b) => b - a).map((v) => ({ value: v, label: String(v) })),
        group: unique((p) => p.insect_group).sort(cmp).map((v) => ({ value: v, label: v })),
        locality: unique((p) => p.locality).sort(cmp).map((v) => ({ value: v, label: v })),
        status
      };
    },
    projectFiltersActive() { return Object.values(this.filters).some((v) => v !== null); },
    projectIndex() {
      const map = {};
      this.projects.forEach((p) => {
        const species = (this.specimensByProject[p.id] || []).map((e) => `${e.species} ${e.family || ''}`).join(' ');
        map[p.id] = norm([p.title, p.insect_group, p.locality, p.year, p.description, p.measured_traits, species].join(' '));
      });
      return map;
    },
    sortLabel() { return this.t(`sort.${this.sortOrder}`); },
    filteredProjects() {
      const f = this.filters;
      const list = this.projects.filter((p) => {
        if (f.year !== null && p.year !== f.year) return false;
        if (f.group !== null && p.insect_group !== f.group) return false;
        if (f.status !== null && (p.finished ? 'finished' : 'in_progress') !== f.status) return false;
        if (f.locality !== null && p.locality !== f.locality) return false;
        return true;
      });
      if (this.sortOrder === 'title') list.sort((a, b) => cmp(a.title, b.title));
      else if (this.sortOrder === 'species') {
        list.sort((a, b) => this.countSpecies(this.specimensOf(b)) - this.countSpecies(this.specimensOf(a)) || cmp(a.title, b.title));
      } else list.sort((a, b) => b.year - a.year || a.id - b.id);
      return list;
    },

    // ---------- global search ----------
    query() { return norm(this.searchTerm).trim(); },
    showSuggestions() { return this.suggestionsOpen && this.query.length >= 2 && this.route.name !== 'search'; },
    globalSpecies() {
      const map = new Map();
      this.specimens.forEach((e) => {
        if (!map.has(e.species)) map.set(e.species, { name: e.species, order: e.insect_order, family: e.family || '', specimens: [] });
        map.get(e.species).specimens.push(e);
      });
      return [...map.values()];
    },
    results() {
      const q = this.query;
      const empty = { projects: [], species: [], specimens: [], repositories: [], pages: [], total: 0 };
      if (q.length < 2) return empty;
      const r = { ...empty };
      r.projects = this.projects.filter((p) => this.projectIndex[p.id].includes(q)).sort((a, b) => b.year - a.year || a.id - b.id);
      r.species = this.globalSpecies
        .filter((x) => norm(`${x.name} ${x.family} ${x.order}`).includes(q))
        .sort((a, b) => cmp(a.name, b.name));
      r.specimens = this.indexedSpecimens
        .filter((i) => norm(`${i.e.catalog_number} ${i.e.locality || ''}`).includes(q))
        .map((i) => i.e);
      r.repositories = this.repositories.filter((x) => norm(`${x.title} ${x.description || ''}`).includes(q));
      const aboutText = norm([this.aboutText, ...this.team.map((m) => `${m.name} ${m.role}`)].join(' '));
      if (aboutText.includes(q)) r.pages = [{ title: this.t('tab.about'), excerpt: this.aboutText }];
      r.total = r.projects.length + r.species.length + r.specimens.length + r.repositories.length + r.pages.length;
      return r;
    },
    searchSuggestions() {
      const r = this.results;
      const list = [];
      r.projects.slice(0, 4).forEach((p) => list.push({ group: this.t('search.projects'), label: p.title, sub: `${p.insect_group} · ${p.year}`, href: this.link('project', { id: p.id }) }));
      r.species.slice(0, 4).forEach((x) => list.push({ group: this.t('search.species'), label: x.name, italic: true, sub: x.family || x.order, species: x.name }));
      r.repositories.slice(0, 2).forEach((x) => list.push({ group: this.t('search.repositories'), label: x.title, sub: 'Zenodo', href: this.link('project', { id: x.id }) }));
      r.specimens.slice(0, 3).forEach((e) => list.push({ group: this.t('search.specimens'), label: e.catalog_number, sub: e.species, href: this.specimenTarget(e) }));
      r.pages.forEach((x) => list.push({ group: this.t('search.pages'), label: x.title, sub: '', href: this.link('about') }));
      return list;
    },

    // ---------- collection ----------
    suggestions() {
      const unique = (list) => [...new Set(list.filter(Boolean))].sort(cmp);
      const vocabulary = (field) => Object.keys(VOCABULARY[field]).map((v) => this.vocab(field, v));
      return {
        groups: unique(this.projects.map((p) => p.insect_group)),
        orders: unique(this.specimens.map((e) => e.insect_order)),
        families: unique(this.specimens.map((e) => e.family)),
        traits: unique(this.specimens.flatMap((e) => (e.measurements || []).map((m) => m.trait))),
        sexes: vocabulary('sex'),
        stages: ['adulto', 'operária', 'soldado', 'rainha', 'ninfa', 'larva', 'pupa'].map((v) => this.vocab('life_stage', v)),
        methods: vocabulary('sampling_method'),
        loan: vocabulary('loan_status')
      };
    },
    repositories() {
      return this.projects
        .filter((p) => isUrl(p.dataset_url))
        .sort((a, b) => b.year - a.year || cmp(a.title, b.title));
    },
    indexedSpecimens() {
      return this.specimens.map((e) => {
        const p = this.projectsById[e.project_id];
        return { e, text: norm([e.species, e.family, e.insect_order, e.catalog_number, e.locality, p ? p.title : ''].join(' ')) };
      });
    },
    baseSpecimens() {
      const q = norm(this.collectionSearch).trim();
      return this.indexedSpecimens.filter((i) => !q || i.text.includes(q)).map((i) => i.e);
    },
    filteredSpecimens() {
      const f = this.collectionFilters;
      return this.baseSpecimens.filter((e) => {
        if (f.orders.length && !f.orders.includes(e.insect_order)) return false;
        if (f.families.length && !f.families.includes(this.familyOf(e))) return false;
        if (f.repos.length && !f.repos.includes(e.project_id)) return false;
        if (f.years.length) {
          const p = this.projectsById[e.project_id];
          if (!p || !f.years.includes(p.year)) return false;
        }
        return true;
      });
    },
    collectionFiltersActive() {
      const f = this.collectionFilters;
      return !!(f.orders.length || f.families.length || f.repos.length || f.years.length);
    },

    orderFacet() {
      return [...countBy(this.baseSpecimens, (e) => e.insect_order)]
        .map(([value, s]) => ({ value, n: s.size })).sort((a, b) => cmp(a.value, b.value));
    },
    familyFacet() {
      const o = this.collectionFilters.orders;
      const base = o.length ? this.baseSpecimens.filter((e) => o.includes(e.insect_order)) : this.baseSpecimens;
      return [...countBy(base, (e) => this.familyOf(e))]
        .map(([value, s]) => ({ value, n: s.size }))
        .sort((a, b) => (a.value === NO_FAMILY) - (b.value === NO_FAMILY) || cmp(a.value, b.value));
    },
    repoFacet() {
      const counts = countBy(this.baseSpecimens, (e) => e.project_id);
      return this.repositories.map((r) => ({ value: r.id, label: r.title, n: counts.has(r.id) ? counts.get(r.id).size : 0 }));
    },
    yearFacet() {
      const map = new Map();
      this.repositories.forEach((r) => map.set(r.year, (map.get(r.year) || 0) + 1));
      return [...map].map(([value, n]) => ({ value, n })).sort((a, b) => b.value - a.value);
    },

    tree() {
      const orders = new Map();
      this.filteredSpecimens.forEach((e) => {
        const fam = this.familyOf(e);
        if (!orders.has(e.insect_order)) orders.set(e.insect_order, new Map());
        const families = orders.get(e.insect_order);
        if (!families.has(fam)) families.set(fam, new Map());
        const species = families.get(fam);
        if (!species.has(e.species)) species.set(e.species, []);
        species.get(e.species).push(e);
      });
      return [...orders].sort(([a], [b]) => cmp(a, b)).map(([name, families]) => {
        const list = [...families]
          .sort(([a], [b]) => (a === NO_FAMILY) - (b === NO_FAMILY) || cmp(a, b))
          .map(([familyName, species]) => ({
            name: familyName,
            species: [...species].sort(([a], [b]) => cmp(a, b)).map(([speciesName, specimens]) => ({
              name: speciesName,
              specimens: specimens.sort((x, y) => cmp(x.catalog_number, y.catalog_number)),
              repos: this.reposOf(specimens)
            }))
          }));
        return {
          name,
          families: list,
          speciesCount: list.reduce((acc, f) => acc + f.species.length, 0)
        };
      });
    },
    totalSpecies() { return this.tree.reduce((acc, o) => acc + o.speciesCount, 0); },

    filteredRepositories() {
      const f = this.collectionFilters;
      const q = norm(this.collectionSearch).trim();
      const withSpecimens = new Set(this.filteredSpecimens.map((e) => e.project_id));
      const filtersSpecimens = f.orders.length || f.families.length;
      return this.repositories.filter((r) => {
        if (f.years.length && !f.years.includes(r.year)) return false;
        if (!filtersSpecimens && !q) return true;
        if (withSpecimens.has(r.id)) return true;
        return !filtersSpecimens && norm(`${r.title} ${r.description || ''}`).includes(q);
      });
    },

    // ---------- gallery, map and panel ----------
    contextList() { return this.route.name === 'project' ? this.projectSpecimens : this.filteredSpecimens; },
    visibleGallery() { return this.contextList.slice(0, this.galleryLimit); },
    galleryRemaining() { return Math.max(this.contextList.length - this.galleryLimit, 0); },
    totalWithImage() { return this.contextList.filter((e) => this.imageUrl(e, 100)).length; },
    mapPoints() {
      return this.contextList
        .filter((e) => e.latitude !== null && e.latitude !== undefined && e.longitude !== null && e.longitude !== undefined)
        .map((e) => ({
          id: e.id, lat: e.latitude, lng: e.longitude, color: this.orderColors[e.insect_order] || '#555',
          species: e.species, code: e.catalog_number, locality: e.locality || '', thumb: this.imageUrl(e, 240)
        }));
    },
    withoutCoordinates() { return this.contextList.length - this.mapPoints.length; },
    mapLegend() {
      const orders = [...new Set(this.contextList.map((e) => e.insect_order))].sort(cmp);
      return orders.map((o) => ({ name: o, color: this.orderColors[o] || '#555' }));
    },
    panelSpecimen() {
      if (!this.panel) return null;
      return this.specimensById[this.panel.ids[this.panel.index]] || null;
    },
    panelProject() { return this.panelSpecimen ? this.projectsById[this.panelSpecimen.project_id] || null : null; }
  },

  watch: {
    pageTitle: { immediate: true, handler(t) { document.title = t; } },
    lang: { immediate: true, handler(lang) { document.documentElement.lang = LOCALES[lang]; } },
    searchTerm(v) {
      this.suggestionIndex = -1;
      this.suggestionsOpen = true;
      if (this.route.name === 'search') {
        history.replaceState(null, '', this.link('search', { q: v.trim() }));
      }
    },
    table: { deep: true, handler() { this.syncTableUrl(); } },
    collectionSearch() { this.galleryLimit = GALLERY_PAGE_SIZE; this.expandIfFiltering(); },
    collectionFilters: { deep: true, handler() { this.galleryLimit = GALLERY_PAGE_SIZE; this.expandIfFiltering(); } }
  },

  created() {
    this.applyRoute();
  },

  async mounted() {
    const token = localStorage.getItem('entomobase_token');
    if (tokenIsValid(token)) {
      this.token = token;
      this.userEmail = localStorage.getItem('entomobase_email');
    } else {
      localStorage.removeItem('entomobase_token');
      localStorage.removeItem('entomobase_email');
    }
    window.addEventListener('hashchange', this.applyRoute);
    document.addEventListener('click', this.closePopups);
    document.addEventListener('keydown', this.onKey);
    await this.loadAll();
    this.expandFirst();
  },

  beforeUnmount() {
    window.removeEventListener('hashchange', this.applyRoute);
    document.removeEventListener('click', this.closePopups);
    document.removeEventListener('keydown', this.onKey);
  },

  methods: {
    isUrl,

    // ---------- texts and formats ----------
    t(key, params = {}) { return translate(this.lang, key, params); },
    describeProblems(problems) { return (problems || []).map((p) => describeProblem(this.lang, p)).join('; '); },
    // formatted number in the current language
    n(value) { return Number(value).toLocaleString(this.locale); },
    fmt(value) { return Number(value).toLocaleString(this.locale, { maximumFractionDigits: 2 }); },
    // "12 espécies" / "12 species"; kind is one of the count.* keys of i18n.js
    count(kind, value) { return this.t(`count.${kind}`, { n: this.n(value), count: value }); },
    vocab(field, value) { return displayValue(this.lang, field, value); },
    familyLabel(name) { return name === NO_FAMILY ? this.t('common.no_family') : name; },

    // ---------- addresses ----------
    // builds the address of a page in a language: link('project', { id: 3, view: 'map' }) -> #/projetos/3/mapa
    link(name, { id, view, q } = {}, lang = this.lang) {
      const w = ROUTE_WORDS[lang];
      const prefix = lang === 'en' ? '#/en/' : '#/';
      if (name === 'project') return `${prefix}${w.projects}/${id}${view && view !== 'table' ? '/' + w[view] : ''}`;
      if (name === 'collection') return `${prefix}${w.collection}${view && view !== 'tree' ? '/' + w[view] : ''}`;
      if (name === 'search') return `${prefix}${w.search}${q ? '/' + encodeURIComponent(q) : ''}`;
      return prefix + w[name];
    },
    // the same page as the current one, in lang (used by the language switch and the table address)
    currentLink(lang = this.lang) {
      const r = this.route;
      if (r.name === 'project') {
        const base = this.link('project', { id: r.id, view: r.view }, lang);
        if (r.view !== 'table') return base;
        const qs = this.tableQuery(lang);
        return base + (qs ? '?' + qs : '');
      }
      if (r.name === 'collection') return this.link('collection', { view: r.view }, lang);
      if (r.name === 'search') return this.link('search', { q: this.searchTerm.trim() }, lang);
      return this.link(r.name, {}, lang);
    },
    switchLanguage() {
      const target = this.lang === 'pt' ? 'en' : 'pt';
      try { localStorage.setItem('entomobase_lang', target); } catch { /* storage unavailable */ }
      location.hash = this.currentLink(target);
    },

    // ---------- project table ----------
    tableQuery(lang) {
      const t = this.table;
      const qs = new URLSearchParams();
      if (this.currentPage > 1) qs.set('p', this.currentPage);
      if (t.perPage !== 25) qs.set('n', t.perPage);
      if (t.sort !== 'catalog') qs.set('o', SORT_WORDS[lang][t.sort] || t.sort);
      if (t.dir !== 'asc') qs.set('d', t.dir);
      if (t.query.trim()) qs.set('q', t.query.trim());
      return qs.toString();
    },
    syncTableUrl() {
      if (this.route.name !== 'project' || this.route.view !== 'table') return;
      const target = this.currentLink();
      if (location.hash !== target) history.replaceState(null, '', target);
    },
    sortBy(key) {
      if (this.table.sort === key) this.table.dir = this.table.dir === 'asc' ? 'desc' : 'asc';
      else { this.table.sort = key; this.table.dir = 'asc'; }
      this.table.page = 1;
    },
    goToPage(n) {
      this.table.page = Math.min(Math.max(1, n), this.totalPages);
      this.$nextTick(() => { const el = document.querySelector('.table-top'); if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' }); });
    },
    ariaSort(key) { return this.table.sort === key ? (this.table.dir === 'asc' ? 'ascending' : 'descending') : 'none'; },

    // ---------- navigation ----------
    // reads the language and the page from the address bar (#/projetos/1 or #/en/projects/1)
    applyRoute() {
      const [path, search = ''] = (location.hash || '').replace(/^#\/?/, '').split('?');
      let parts = path.split('/').filter(Boolean);
      let lang = 'pt';
      if (parts[0] === 'en') { lang = 'en'; parts = parts.slice(1); }
      else if (!parts.length) {
        // first visit without an address: the saved choice, otherwise the browser language
        const preferred = savedLanguage() || ((navigator.language || '').toLowerCase().startsWith('en') ? 'en' : 'pt');
        if (preferred === 'en') { location.replace(this.link('about', {}, 'en')); return; }
      }
      this.lang = lang;
      const [a, b, c] = parts;
      const page = wordKey(ROUTE_WORDS, a);
      const qs = new URLSearchParams(search);
      let route;
      if (page === 'projects') {
        const view = wordKey(ROUTE_WORDS, c);
        route = b ? { name: 'project', id: Number(b), view: ['gallery', 'map'].includes(view) ? view : 'table' } : { name: 'projects' };
      } else if (page === 'collection') {
        const view = wordKey(ROUTE_WORDS, b);
        route = { name: 'collection', view: ['repos', 'map'].includes(view) ? view : 'tree' };
      } else if (page === 'search') route = { name: 'search' };
      else route = { name: 'about' };
      const previous = this.route;
      const samePage = !!previous && previous.name === route.name && previous.id === route.id && !!route.name && (route.name === 'project' || route.name === 'collection');
      this.route = route;
      if (route.name === 'project') {
        const n = Number(qs.get('n'));
        const sortWord = qs.get('o');
        this.table = {
          page: Math.max(1, Number(qs.get('p')) || 1),
          perPage: this.pageSizes.includes(n) ? n : 25,
          sort: wordKey(SORT_WORDS, sortWord) || (sortWord && sortWord.startsWith('m:') ? sortWord : 'catalog'),
          dir: qs.get('d') === 'desc' ? 'desc' : 'asc',
          query: qs.get('q') || ''
        };
      }
      this.closePopups();
      this.galleryLimit = GALLERY_PAGE_SIZE;
      if (route.name === 'search') {
        try { this.searchTerm = decodeURIComponent(b || ''); } catch { this.searchTerm = b || ''; }
      } else {
        this.searchTerm = '';
      }
      if (route.name === 'collection') {
        if (route.view === 'repos') this.collectionFilters.repos = [];
        else this.collectionFilters.years = [];
      }
      // switching views (table, gallery, map) keeps the scroll position
      if (!samePage) window.scrollTo(0, 0);
    },
    closePopups() { this.openMenu = null; this.popover = null; this.suggestionsOpen = false; },
    onKey(ev) {
      const modalOpen = this.confirmation || this.specimenForm || this.projectForm || this.importJob || this.info || this.showLogin;
      if (this.panel && !modalOpen) {
        if (ev.key === 'ArrowLeft') { this.movePanel(-1); return; }
        if (ev.key === 'ArrowRight') { this.movePanel(1); return; }
      }
      if (ev.key !== 'Escape') return;
      this.closePopups();
      if (this.confirmation) this.confirmation = null;
      else if (this.specimenForm) this.specimenForm = null;
      else if (this.projectForm) this.projectForm = null;
      else if (this.importJob) this.importJob = null;
      else if (this.info) this.info = null;
      else if (this.showLogin) this.showLogin = false;
      else if (this.panel) this.panel = null;
    },
    notify(msg) {
      this.toast = msg;
      clearTimeout(this.toastTimer);
      this.toastTimer = setTimeout(() => { this.toast = null; }, 4500);
    },

    // ---------- API ----------
    // the API sends {"detail": {"code", "params", "problems"?}}; the message comes from i18n.js
    async errorMessage(res) {
      try {
        const d = (await res.json()).detail;
        if (d && typeof d === 'object' && !Array.isArray(d) && d.code) {
          if (d.problems && d.problems.length) return this.describeProblems(d.problems);
          return this.t(`error.${d.code}`, d.params || {});
        }
        if (typeof d === 'string') return d;
      } catch { /* response without a JSON body */ }
      return this.t('error.unknown', { status: res.status });
    },
    async api(path, { method = 'GET', body = null } = {}) {
      const headers = {};
      if (body !== null) headers['Content-Type'] = 'application/json';
      if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
      let res;
      try {
        res = await fetch(this.apiUrl + path, { method, headers, body: body !== null ? JSON.stringify(body) : undefined });
      } catch {
        throw new Error(this.t('error.connection'));
      }
      if (res.status === 401 && this.token && path !== '/login') {
        this.endSession();
        this.loginError = this.t('error.session_expired_login');
        this.showLogin = true;
        this.projectForm = this.specimenForm = this.confirmation = this.importJob = null;
        throw new Error(this.t('error.session_expired_short'));
      }
      if (!res.ok) throw new Error(await this.errorMessage(res));
      return res.status === 204 ? null : res.json();
    },
    async loadAll() {
      this.loading = true;
      this.apiError = null;
      try {
        const [projects, specimens] = await Promise.all([this.api('/projects'), this.api('/specimens')]);
        this.projects = projects;
        this.specimens = specimens;
      } catch (e) {
        this.apiError = e.message;
      }
      this.loading = false;
    },

    // ---------- session ----------
    openLogin() { this.loginError = null; this.showLogin = true; },
    async login() {
      this.loginError = null;
      this.submitting = true;
      try {
        const d = await this.api('/login', { method: 'POST', body: this.credentials });
        this.token = d.access_token;
        this.userEmail = d.email;
        localStorage.setItem('entomobase_token', this.token);
        localStorage.setItem('entomobase_email', this.userEmail);
        this.showLogin = false;
        this.credentials = { email: '', password: '' };
        await this.loadAll();
      } catch (e) {
        this.loginError = e.message;
      }
      this.submitting = false;
    },
    endSession() {
      this.token = null;
      this.userEmail = null;
      localStorage.removeItem('entomobase_token');
      localStorage.removeItem('entomobase_email');
    },
    async logout() {
      this.endSession();
      await this.loadAll();
    },

    // ---------- display helpers ----------
    specimensOf(p) { return this.specimensByProject[p.id] || []; },
    countSpecies(list) { return new Set((list || []).map((e) => e.species)).size; },
    statusLabel(p) { return p.finished ? this.t('status.finished') : this.t('status.in_progress'); },
    coverColor(p) { return COVER_PALETTE[(p.id - 1 + COVER_PALETTE.length) % COVER_PALETTE.length]; },
    coverStyle(p) {
      const style = { backgroundColor: this.coverColor(p) };
      if (isUrl(p.cover_url)) {
        style.backgroundImage = `url("${p.cover_url.trim().replace(/"/g, '%22')}")`;
        style.backgroundSize = 'cover';
        style.backgroundPosition = 'center';
      }
      return style;
    },
    familyOf(e) { return e.family || NO_FAMILY; },
    // dd/mm/yyyy in Portuguese, yyyy-mm-dd in English
    formatDate(d) {
      if (!d) return '—';
      const [y, m, day] = d.split('-');
      return this.lang === 'en' ? `${y}-${m}-${day}` : `${day}/${m}/${y}`;
    },
    measurementValue(e, column) {
      const m = (e.measurements || []).find((x) => `${x.trait}|${x.unit}` === column.key);
      return m ? this.fmt(m.value) : '—';
    },
    measurementSummary(e, n = 3) {
      return (e.measurements || []).slice(0, n).map((m) => ({ trait: m.trait, text: `${this.fmt(m.value)} ${m.unit}` }));
    },
    orderColor(o) { return this.orderColors[o] || '#555'; },
    reposOf(specimens) {
      const ids = [...new Set(specimens.map((e) => e.project_id))];
      return ids
        .map((id) => this.projectsById[id])
        .filter((p) => p && isUrl(p.dataset_url))
        .sort((a, b) => b.year - a.year)
        .map((p) => ({ id: p.id, title: p.title, url: p.dataset_url.trim() }));
    },
    repositorySummary(r) {
      const list = this.specimensOf(r);
      const orders = [...new Set(list.map((e) => e.insect_order))].sort(cmp);
      const parts = [this.count('species', this.countSpecies(list))];
      if (orders.length) parts.push(orders.join(', '));
      parts.push(String(r.year));
      return parts.join(' · ');
    },

    // ---------- images (Zenodo) ----------
    recordIdOf(e) { return Zenodo.recordId((this.projectsById[e.project_id] || {}).dataset_url); },
    imageUrl(e, width = 400) {
      if (isUrl(e.photo_url)) return e.photo_url.trim();
      if (!e.image_file) return null;
      const id = this.recordIdOf(e);
      if (!id) return null;
      if (Zenodo.isDemo(id)) return `${this.apiUrl}/demo/image/${encodeURIComponent(e.image_file)}`;
      return Zenodo.thumbnail(id, e.image_file, width);
    },
    fileUrl(e) {
      if (!e.image_file) return isUrl(e.photo_url) ? e.photo_url.trim() : null;
      const id = this.recordIdOf(e);
      if (!id) return null;
      return Zenodo.isDemo(id) ? null : Zenodo.file(id, e.image_file);
    },
    recordUrl(e) {
      const p = this.projectsById[e.project_id];
      return p && isUrl(p.dataset_url) ? p.dataset_url.trim() : null;
    },

    // ---------- detail panel ----------
    openPanel(e, list) {
      const ids = (list && list.length ? list : [e]).map((x) => x.id);
      this.panel = { ids, index: Math.max(0, ids.indexOf(e.id)) };
    },
    openPanelById(id) {
      const e = this.specimensById[id];
      if (e) this.openPanel(e, this.contextList);
    },
    movePanel(step) {
      const n = this.panel.ids.length;
      this.panel.index = (this.panel.index + step + n) % n;
    },
    showOnMap(e) {
      this.mapFocus = e.id;
      this.panel = null;
      const target = this.route.name === 'project' ? this.link('project', { id: this.route.id, view: 'map' }) : this.link('collection', { view: 'map' });
      if (location.hash === target) return;
      location.hash = target;
    },
    specimenTarget(e) { return e.project_id ? this.link('project', { id: e.project_id }) : this.link('collection'); },
    editFromPanel(e) { this.panel = null; this.openSpecimenForm(e); },
    deleteFromPanel(e) { this.panel = null; this.askDeleteSpecimen(e); },

    // ---------- global search ----------
    moveSuggestion(step) {
      const n = this.searchSuggestions.length;
      if (!n) return;
      this.suggestionsOpen = true;
      let i = this.suggestionIndex + step;
      if (i < 0) i = n - 1;
      if (i >= n) i = 0;
      this.suggestionIndex = i;
    },
    chooseSuggestion(s) {
      this.suggestionsOpen = false;
      if (s.species) this.openSpecies(s.species);
      else location.hash = s.href;
    },
    submitSearch(force = false) {
      if (!force && this.suggestionIndex >= 0 && this.searchSuggestions[this.suggestionIndex]) {
        this.chooseSuggestion(this.searchSuggestions[this.suggestionIndex]);
        return;
      }
      const t = this.searchTerm.trim();
      if (!t) return;
      this.suggestionsOpen = false;
      location.hash = this.link('search', { q: t });
    },
    openSpecies(name) {
      this.collectionFilters = { orders: [], families: [], repos: [], years: [] };
      this.collectionSearch = name;
      location.hash = this.link('collection');
    },

    // ---------- project filters ----------
    toggleMenu(key) { this.popover = null; this.openMenu = this.openMenu === key ? null : key; },
    setFilter(key, value) { this.filters[key] = value; this.openMenu = null; },
    filterLabel(f) {
      const v = this.filters[f.key];
      if (v === null) return f.label;
      const option = this.filterOptions[f.key].find((o) => o.value === v);
      return `${f.label}: ${option ? option.label : v}`;
    },
    clearProjectFilters() { this.filters = { year: null, group: null, status: null, locality: null }; },

    // ---------- collection tree ----------
    isExpanded(key) { return !!this.expanded[key]; },
    toggle(key) { this.expanded[key] = !this.expanded[key]; this.popover = null; },
    togglePopover(key) { this.openMenu = null; this.popover = this.popover === key ? null : key; },
    expandAll() {
      const expanded = {};
      this.tree.forEach((o) => {
        expanded[`o:${o.name}`] = true;
        o.families.forEach((f) => { expanded[`f:${o.name}|${f.name}`] = true; });
      });
      this.expanded = expanded;
    },
    collapseAll() { this.expanded = {}; },
    expandFirst() {
      const o = this.tree[0];
      if (!o || Object.keys(this.expanded).length) return;
      this.expanded[`o:${o.name}`] = true;
      o.families.forEach((f) => { this.expanded[`f:${o.name}|${f.name}`] = true; });
    },
    expandIfFiltering() {
      if (this.collectionSearch.trim() || this.collectionFiltersActive) this.$nextTick(() => this.expandAll());
    },
    clearCollectionFilters() {
      this.collectionFilters = { orders: [], families: [], repos: [], years: [] };
      this.collectionSearch = '';
    },

    // ---------- projects: create, edit, delete ----------
    openProjectForm(p = null) {
      this.formError = null;
      this.projectForm = p
        ? {
            id: p.id, title: p.title, year: p.year, insect_group: p.insect_group, measured_traits: p.measured_traits || '',
            locality: p.locality || '', cover_url: p.cover_url || '', dataset_url: p.dataset_url || '',
            linked_publication: p.linked_publication || '', description: p.description || '', finished: !!p.finished,
            visibility: p.visibility || 'private'
          }
        : {
            id: null, title: '', year: new Date().getFullYear(), insect_group: '', measured_traits: '', locality: '',
            cover_url: '', dataset_url: '', linked_publication: '', description: '', finished: false,
            visibility: 'private'
          };
    },
    async saveProject() {
      const f = this.projectForm;
      this.formError = null;
      this.submitting = true;
      const body = {
        title: f.title.trim(), year: Number(f.year), insect_group: f.insect_group.trim(),
        measured_traits: orNull(f.measured_traits), locality: orNull(f.locality), cover_url: orNull(f.cover_url),
        dataset_url: orNull(f.dataset_url), linked_publication: orNull(f.linked_publication),
        description: orNull(f.description), finished: !!f.finished, visibility: f.visibility
      };
      try {
        const saved = await this.api(f.id ? `/projects/${f.id}` : '/projects', { method: f.id ? 'PUT' : 'POST', body });
        this.projectForm = null;
        await this.loadAll();
        this.notify(this.t(f.id ? 'notify.project_updated' : 'notify.project_created'));
        if (!f.id) location.hash = this.link('project', { id: saved.id });
      } catch (e) {
        this.formError = e.message;
      }
      this.submitting = false;
    },
    askDeleteProject(p) {
      this.formError = null;
      const n = this.specimensOf(p).length;
      this.confirmation = {
        title: this.t('confirm.project_title'),
        text: this.t('confirm.project_text', { title: p.title, with: n ? this.count('specimen', n) : '' }),
        action: async () => {
          await this.api(`/projects/${p.id}`, { method: 'DELETE' });
          location.hash = this.link('projects');
          await this.loadAll();
          this.notify(this.t('notify.project_deleted'));
        }
      };
    },

    // ---------- specimens: create, edit, delete ----------
    // values with a fixed vocabulary are shown in the current language and stored in Portuguese on save
    openSpecimenForm(e = null, projectId = null) {
      this.formError = null;
      this.nameHint = null;
      if (e) {
        this.specimenForm = {
          id: e.id, catalog_number: e.catalog_number, insect_order: e.insect_order, family: e.family || '',
          species: e.species, collection_date: e.collection_date || '', locality: e.locality || '',
          latitude: e.latitude ?? '', longitude: e.longitude ?? '', elevation_m: e.elevation_m ?? '',
          sex: this.vocab('sex', e.sex) || '', life_stage: this.vocab('life_stage', e.life_stage) || '',
          image_file: e.image_file || '', photo_url: e.photo_url || '',
          notes: e.notes || '', project_id: e.project_id ?? null,
          identified_by: e.identified_by || '', identification_date: e.identification_date || '',
          sampling_method: this.vocab('sampling_method', e.sampling_method) || '', habitat: e.habitat || '',
          collector: e.collector || '', field_number: e.field_number || '', storage_location: e.storage_location || '',
          loan_status: this.vocab('loan_status', e.loan_status) || '', loaned_to: e.loaned_to || '', loan_date: e.loan_date || '',
          internal_notes: e.internal_notes || '',
          measurements: (e.measurements || []).map((m) => ({ trait: m.trait, value: m.value, unit: m.unit }))
        };
      } else {
        const project = this.projectsById[projectId];
        const traits = project && project.measured_traits ? project.measured_traits.split(',').map((t) => t.trim()).filter(Boolean) : [];
        this.specimenForm = {
          id: null, catalog_number: '', insect_order: '', family: '', species: '', collection_date: '', locality: project ? project.locality || '' : '',
          latitude: '', longitude: '', elevation_m: '', sex: '', life_stage: '', image_file: '', photo_url: '',
          notes: '', project_id: projectId,
          identified_by: '', identification_date: '', sampling_method: '', habitat: '',
          collector: '', field_number: '', storage_location: '', loan_status: '', loaned_to: '', loan_date: '', internal_notes: '',
          measurements: traits.map((t) => ({ trait: t, value: '', unit: 'mm' }))
        };
      }
    },
    async checkName() {
      const f = this.specimenForm;
      const name = (f.species || '').trim();
      this.nameHint = null;
      if (name.split(/\s+/).length < 2) return;
      try {
        const [r] = await this.api('/taxonomy/validate', { method: 'POST', body: { names: [name] } });
        if (!r || f.species.trim() !== name) return;
        if (r.status === 'ok' || r.status === 'unavailable') {
          if (r.status === 'ok') {
            if (!f.family && r.family) f.family = r.family;
            if (!f.insect_order && r.order_name) f.insect_order = r.order_name;
          }
          return;
        }
        this.nameHint = { name, status: r.status, suggestion: r.suggestion };
      } catch { /* no validation if GBIF or the API do not answer */ }
    },
    useSuggestedName() {
      this.specimenForm.species = this.nameHint.suggestion;
      this.nameHint = null;
      this.checkName();
    },
    addMeasurement() { this.specimenForm.measurements.push({ trait: '', value: '', unit: 'mm' }); },
    removeMeasurement(i) { this.specimenForm.measurements.splice(i, 1); },
    async saveSpecimen() {
      const f = this.specimenForm;
      this.formError = null;
      const measurements = [];
      for (const m of f.measurements) {
        const value = num(m.value);
        const trait = (m.trait || '').trim();
        if (value === null && !trait) continue;
        if (value === null) continue;
        if (!trait) { this.formError = this.t('sf.trait_required'); return; }
        measurements.push({ trait, value, unit: (m.unit || 'mm').trim() || 'mm' });
      }
      const stored = (field) => storedValue(field, orNull(f[field]));
      const body = {
        catalog_number: f.catalog_number.trim(), insect_order: f.insect_order.trim(), family: orNull(f.family),
        species: f.species.trim(), collection_date: orNull(f.collection_date), locality: orNull(f.locality),
        latitude: num(f.latitude), longitude: num(f.longitude), elevation_m: num(f.elevation_m),
        sex: stored('sex'), life_stage: stored('life_stage'), image_file: orNull(f.image_file), photo_url: orNull(f.photo_url),
        notes: orNull(f.notes), project_id: f.project_id || null, measurements,
        identified_by: orNull(f.identified_by), identification_date: orNull(f.identification_date), sampling_method: stored('sampling_method'), habitat: orNull(f.habitat),
        collector: orNull(f.collector), field_number: orNull(f.field_number), storage_location: orNull(f.storage_location),
        loan_status: stored('loan_status'), loaned_to: orNull(f.loaned_to), loan_date: orNull(f.loan_date),
        internal_notes: orNull(f.internal_notes)
      };
      this.submitting = true;
      try {
        await this.api(f.id ? `/specimens/${f.id}` : '/specimens', { method: f.id ? 'PUT' : 'POST', body });
        this.specimenForm = null;
        await this.loadAll();
        this.notify(this.t(f.id ? 'notify.specimen_updated' : 'notify.specimen_added'));
      } catch (e) {
        this.formError = e.message;
      }
      this.submitting = false;
    },
    askDeleteSpecimen(e) {
      this.formError = null;
      this.confirmation = {
        title: this.t('confirm.specimen_title'),
        text: this.t('confirm.specimen_text', { code: e.catalog_number, species: e.species }),
        action: async () => {
          await this.api(`/specimens/${e.id}`, { method: 'DELETE' });
          await this.loadAll();
          this.notify(this.t('notify.specimen_deleted'));
        }
      };
    },
    async runConfirmation() {
      this.submitting = true;
      this.formError = null;
      try {
        await this.confirmation.action();
        this.confirmation = null;
      } catch (e) {
        if (this.confirmation) this.formError = e.message;
      }
      this.submitting = false;
    },

    // ---------- CSV import ----------
    openImport(projectId = null) {
      const p = this.projectsById[projectId];
      this.importJob = {
        fixedProject: projectId !== null, projectId, projectName: p ? p.title : '',
        fileName: '', headers: [], mapping: [], data: [], duplicates: 'ignore',
        defaults: { insect_order: '', family: '', species: '' },
        clientErrors: [], payloadRows: [], report: null, checking: false, error: null, seq: 0, corrections: {}
      };
    },
    async readImportFile(ev) {
      const file = ev.target.files && ev.target.files[0];
      if (!file) return;
      const job = this.importJob;
      job.error = null;
      try {
        const rows = parseCsv(await file.text());
        if (rows.length < 2) throw new Error(this.t('import.need_rows'));
        if (rows.length - 1 > 5000) throw new Error(this.t('import.too_many'));
        job.fileName = file.name;
        job.headers = rows[0].map((h) => h.trim());
        job.mapping = job.headers.map((h) => interpretHeader(h));
        job.data = rows.slice(1);
        await this.runDryRun();
      } catch (e) {
        job.error = e.message;
      }
      ev.target.value = '';
    },
    buildImportRows() {
      const job = this.importJob;
      const rows = [];
      const errors = [];
      job.data.forEach((cells, k) => {
        const line = k + 2;
        const o = { line };
        const problems = [];
        job.mapping.forEach((col, i) => {
          const raw = (cells[i] ?? '').trim();
          if (raw === '' || col.target === 'ignore') return;
          if (col.target === 'measurement') {
            const value = parseNumber(raw);
            if (Number.isNaN(value)) { problems.push({ code: 'invalid_measurement', params: { trait: col.trait, value: raw } }); return; }
            (o.measurements = o.measurements || []).push({ trait: col.trait, value, unit: col.unit || 'mm' });
            return;
          }
          const field = col.target.slice(6);
          if (['latitude', 'longitude', 'elevation_m'].includes(field)) {
            const v = parseNumber(raw);
            if (Number.isNaN(v)) problems.push({ code: 'invalid_value', field, params: { value: raw } }); else o[field] = v;
          } else if (['collection_date', 'identification_date', 'loan_date'].includes(field)) o[field] = toIsoDate(raw);
          else if (field === 'project') {
            const p = this.projects.find((x) => norm(x.title) === norm(raw));
            if (p) o.project_id = p.id; else problems.push({ code: 'project_title_not_found', params: { title: raw } });
          } else if (field === 'project_id') {
            const v = parseNumber(raw);
            if (Number.isNaN(v)) problems.push({ code: 'invalid_project_id', params: { value: raw } }); else o.project_id = v;
          } else if (VOCABULARY_FIELDS.includes(field)) o[field] = storedValue(field, raw);
          else o[field] = raw;
        });
        ['insect_order', 'family', 'species'].forEach((c) => {
          if (!o[c] && job.defaults[c].trim()) o[c] = job.defaults[c].trim();
        });
        if (o.species && job.corrections[o.species]) o.species = job.corrections[o.species];
        if (problems.length) errors.push({ line, catalog_number: o.catalog_number || '', problems });
        else rows.push(o);
      });
      return { rows, errors };
    },
    scheduleDryRun() {
      clearTimeout(this.dryRunTimer);
      this.dryRunTimer = setTimeout(() => this.runDryRun(), 350);
    },
    async runDryRun() {
      const job = this.importJob;
      if (!job || !job.data.length) return;
      const seq = ++job.seq;
      const { rows, errors } = this.buildImportRows();
      job.clientErrors = errors;
      job.payloadRows = rows;
      job.error = null;
      if (!rows.length) { job.report = null; return; }
      job.checking = true;
      try {
        const report = await this.api('/specimens/import?dry_run=true', {
          method: 'POST', body: { project_id: job.projectId || null, duplicates: job.duplicates, rows }
        });
        if (seq === job.seq) job.report = report;
      } catch (e) {
        if (seq === job.seq) { job.report = null; job.error = e.message; }
      }
      if (seq === job.seq) job.checking = false;
    },
    async confirmImport() {
      const job = this.importJob;
      job.submitting = true;
      job.error = null;
      try {
        const report = await this.api('/specimens/import', {
          method: 'POST', body: { project_id: job.projectId || null, duplicates: job.duplicates, rows: job.payloadRows }
        });
        this.importJob = null;
        await this.loadAll();
        const parts = [];
        if (report.created) parts.push(this.count('created', report.created));
        if (report.updated) parts.push(this.count('updated', report.updated));
        if (report.skipped) parts.push(this.count('skipped', report.skipped));
        this.notify(this.t('import.done', { parts: parts.join(', ') || this.t('import.nothing_new') }));
      } catch (e) {
        job.error = e.message;
        job.submitting = false;
      }
    },
    applySuggestion(w) {
      this.importJob.corrections[w.name] = w.suggestion;
      this.runDryRun();
    },
    applyAllSuggestions() {
      (this.importJob.report?.warnings || []).forEach((w) => {
        if (w.suggestion && (w.kind === 'fuzzy' || w.kind === 'synonym')) this.importJob.corrections[w.name] = w.suggestion;
      });
      this.runDryRun();
    },
    warningLabel(kind) { return this.t(`warning.${kind}`); },
    downloadTemplate() {
      const job = this.importJob;
      const p = this.projectsById[job.projectId];
      const traits = p && p.measured_traits ? p.measured_traits.split(',').map((t) => `${t.trim()} (mm)`) : [`${this.t('template.default_trait')} (mm)`];
      const header = [...this.t('template.header'), ...traits];
      const example = [...this.t('template.example'), ...traits.map(() => '6.5')];
      this.downloadText('﻿' + [header, example].map((l) => l.join(',')).join('\n'), `${this.t('file.import_template')}.csv`);
    },
    downloadText(text, name) {
      const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },

    // ---------- export and footer ----------
    async downloadFromApi(path, name) {
      try {
        const res = await fetch(this.apiUrl + path, { headers: this.token ? { Authorization: `Bearer ${this.token}` } : {} });
        if (!res.ok) throw new Error(await this.errorMessage(res));
        const url = URL.createObjectURL(await res.blob());
        const el = document.createElement('a');
        el.href = url;
        el.download = name;
        document.body.appendChild(el);
        el.click();
        el.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        this.notify(e.message === 'Failed to fetch' ? this.t('error.connection') : e.message);
      }
    },
    exportCsv(projectId = null, full = false) {
      const params = [`lang=${this.lang}`];
      if (projectId) params.push(`project_id=${projectId}`);
      if (full) params.push('full=true');
      const base = projectId ? this.t('file.project_csv', { id: projectId }) : this.t('file.collection_csv');
      const name = base + (full ? this.t('file.full_suffix') : '') + '.csv';
      this.downloadFromApi('/export/csv?' + params.join('&'), name);
    },
    exportDwc(projectId = null) {
      const name = projectId ? this.t('file.project_dwc', { id: projectId }) : this.t('file.collection_dwc');
      this.downloadFromApi('/export/dwc' + (projectId ? `?project_id=${projectId}` : ''), `${name}.zip`);
    },
    openInfo(which) { this.info = which; },
    async copyCitation() {
      try {
        await navigator.clipboard.writeText(this.citationText);
        this.notify(this.t('notify.citation_copied'));
      } catch {
        this.notify(this.t('notify.copy_failed'));
      }
    }
  }
});

// ------------------------------------------------------------ components
app.directive('autofocus', { mounted(el) { el.focus({ preventScroll: true }); } });

app.component('icon', {
  props: ['name'],
  computed: { path() { return ICONS[this.name] || ''; } },
  template: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" v-html="path"></svg>'
});

// marks the parts of the text that match the search, ignoring accents
app.component('highlight', {
  props: ['text', 'q'],
  computed: {
    parts() {
      const t = (this.text ?? '').toString();
      const n = norm(t);
      if (!this.q || n.length !== t.length) return [{ t, m: false }];
      const parts = [];
      let i = 0;
      let j;
      while ((j = n.indexOf(this.q, i)) !== -1) {
        if (j > i) parts.push({ t: t.slice(i, j), m: false });
        parts.push({ t: t.slice(j, j + this.q.length), m: true });
        i = j + this.q.length;
      }
      if (i < t.length) parts.push({ t: t.slice(i), m: false });
      return parts.length ? parts : [{ t, m: false }];
    }
  },
  template: '<span><template v-for="(p, i) in parts" :key="i"><mark v-if="p.m">{{ p.t }}</mark><template v-else>{{ p.t }}</template></template></span>'
});

// image with a placeholder frame when the file does not exist or fails to load
app.component('photo', {
  props: ['src', 'alt', 'label'],
  data() { return { failed: false }; },
  watch: { src() { this.failed = false; } },
  template: '<div :class="[\'photo-frame\', { empty: !src || failed }]"><img v-if="src && !failed" :src="src" :alt="alt" loading="lazy" decoding="async" @error="failed = true"><span v-else class="photo-missing">{{ label || $root.t(\'photo.none\') }}</span></div>'
});

app.component('gallery', {
  props: ['items', 'remaining'],
  emits: ['open', 'more'],
  template: '#tpl-gallery'
});

// collection map (Leaflet + point clustering)
app.component('collection-map', {
  props: ['points', 'focus'],
  emits: ['open', 'focused'],
  data() { return { unavailable: false, leafletMap: null, cluster: null, markers: {} }; },
  template: '<div class="map-box"><div ref="el" class="map" role="application" :aria-label="$root.t(\'map.aria\')"></div><p v-if="unavailable" class="map-error">{{ $root.t(\'map.unavailable\') }}</p></div>',
  mounted() {
    if (typeof L === 'undefined' || !L.markerClusterGroup) { this.unavailable = true; return; }
    const map = L.map(this.$refs.el, { scrollWheelZoom: false, worldCopyJump: true }).setView([-15, -47], 4);
    // Esri tiles: no API key and no Referer required (OpenStreetMap and CARTO block in these cases)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19, attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors'
    }).addTo(map);
    map.on('click', () => map.scrollWheelZoom.enable());
    map.getContainer().addEventListener('mouseleave', () => map.scrollWheelZoom.disable());
    this.leafletMap = markRaw(map);
    this.draw(true);
    this.$nextTick(() => { map.invalidateSize(); this.applyFocus(); });
  },
  beforeUnmount() { if (this.leafletMap) this.leafletMap.remove(); },
  watch: {
    points() { this.draw(true); },
    focus() { this.applyFocus(); }
  },
  methods: {
    popup(p) {
      const node = document.createElement('div');
      node.className = 'pop';
      if (p.thumb) {
        const img = document.createElement('img');
        img.src = p.thumb;
        img.alt = p.species;
        img.onerror = () => img.remove();
        node.appendChild(img);
      }
      const name = document.createElement('strong');
      name.className = 'pop-species';
      name.textContent = p.species;
      const line = document.createElement('span');
      line.className = 'pop-line';
      line.textContent = p.code + (p.locality ? ' · ' + p.locality : '');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'pop-button';
      button.textContent = this.$root.t('map.details');
      button.addEventListener('click', () => this.$emit('open', p.id));
      node.append(name, line, button);
      return node;
    },
    draw(fit) {
      if (!this.leafletMap) return;
      if (this.cluster) this.leafletMap.removeLayer(this.cluster);
      const cluster = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 42 });
      const markers = {};
      (this.points || []).forEach((p) => {
        const icon = L.divIcon({ className: 'dot-wrap', html: `<span class="dot" style="background:${p.color}"></span>`, iconSize: [18, 18], iconAnchor: [9, 9], popupAnchor: [0, -10] });
        const m = L.marker([p.lat, p.lng], { icon, title: `${p.species} (${p.code})` });
        m.bindPopup(() => this.popup(p), { minWidth: 190, maxWidth: 240 });
        markers[p.id] = m;
        cluster.addLayer(m);
      });
      this.leafletMap.addLayer(cluster);
      this.cluster = markRaw(cluster);
      this.markers = markRaw(markers);
      if (fit) {
        if ((this.points || []).length) this.leafletMap.fitBounds(cluster.getBounds().pad(0.15), { maxZoom: 13 });
        else this.leafletMap.setView([-15, -47], 4);
      }
      this.applyFocus();
    },
    applyFocus() {
      if (!this.leafletMap || !this.focus) return;
      const m = this.markers[this.focus];
      if (!m) return;
      this.cluster.zoomToShowLayer(m, () => m.openPopup());
      this.$emit('focused');
    }
  }
});

app.mount('#app');
