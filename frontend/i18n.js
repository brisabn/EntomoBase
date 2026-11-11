// every text the site shows, per language; app.js reads them through translate()
// a message is a string or a function that receives the params sent with it

const plural = (n, one, many) => (n === 1 ? one : many);

const MESSAGES = {
  pt: {
    // errors sent by the API as {"code": ..., "params": ...}
    'error.missing_token': 'Token ausente ou inválido',
    'error.session_expired': 'Sessão expirada. Faça login novamente.',
    'error.invalid_credentials': 'E-mail ou senha incorretos',
    'error.too_many_attempts': (p) => `Muitas tentativas. Tente novamente em ${p.minutes} ${plural(p.minutes, 'minuto', 'minutos')}.`,
    'error.project_not_found': 'Projeto não encontrado',
    'error.specimen_not_found': 'Espécime não encontrado.',
    'error.duplicate_catalog_number': 'Código de etiqueta já cadastrado.',
    'error.import_has_errors': (p) => `${p.count} linha(s) com erro; nada foi importado.`,
    'error.full_csv_requires_login': 'O CSV completo exige login.',
    'error.image_not_found': 'Imagem não encontrada',
    'error.unknown': (p) => `Erro ${p.status}`,

    // problems in a single value; p.label is the field name in this language
    'problem.required': (p) => `${p.label}: campo obrigatório`,
    'problem.empty': (p) => `${p.label}: não pode ficar vazio`,
    'problem.max': (p) => `${p.label}: deve ser no máximo ${p.limit}`,
    'problem.min': (p) => `${p.label}: deve ser no mínimo ${p.limit}`,
    'problem.invalid_value': (p) => (p.value !== undefined ? `${p.label}: valor inválido (${p.value})` : `${p.label}: valor inválido`),
    'problem.invalid_measurement': (p) => `valor inválido em "${p.trait}": ${p.value}`,
    'problem.unknown_project': (p) => `projeto_id ${p.project_id} não existe`,
    'problem.duplicate_in_file': (p) => `código repetido no arquivo (primeira vez na linha ${p.first_line})`,
    'problem.project_title_not_found': (p) => `projeto "${p.title}" não encontrado`,
    'problem.invalid_project_id': (p) => `projeto_id inválido (${p.value})`,

    // field names used in problems
    'field.catalog_number': 'Código da etiqueta', 'field.insect_order': 'Ordem', 'field.family': 'Família',
    'field.species': 'Espécie', 'field.collection_date': 'Data da coleta', 'field.locality': 'Local de coleta',
    'field.latitude': 'Latitude', 'field.longitude': 'Longitude', 'field.elevation_m': 'Altitude (m)',
    'field.sex': 'Sexo', 'field.life_stage': 'Estágio', 'field.image_file': 'Arquivo da imagem',
    'field.photo_url': 'URL da fotografia', 'field.notes': 'Notas', 'field.project_id': 'Projeto',
    'field.identified_by': 'Determinador', 'field.identification_date': 'Data da determinação',
    'field.sampling_method': 'Método de coleta', 'field.habitat': 'Habitat', 'field.collector': 'Coletor',
    'field.field_number': 'Número de campo', 'field.storage_location': 'Localização física',
    'field.loan_status': 'Empréstimo', 'field.loaned_to': 'Emprestado para', 'field.loan_date': 'Data do empréstimo',
    'field.internal_notes': 'Notas internas', 'field.title': 'Título', 'field.year': 'Ano',
    'field.insect_group': 'Grupo de insetos', 'field.email': 'E-mail', 'field.password': 'Senha',
    'field.measurement': (p) => `Medida ${p.n}`, 'field.trait': 'traço', 'field.value': 'valor', 'field.unit': 'unidade',

    // downloaded files (names without extension) and the import template
    'file.collection_csv': 'acervo_entomobase', 'file.project_csv': (p) => `projeto_${p.id}_especimes`,
    'file.full_suffix': '_completo', 'file.collection_dwc': 'entomobase_darwincore',
    'file.project_dwc': (p) => `projeto_${p.id}_darwincore`, 'file.import_template': 'modelo_importacao_entomobase',
    'template.default_trait': 'Comprimento corporal',
    'template.header': ['Codigo Etiqueta', 'Ordem', 'Familia', 'Especie', 'Data Coleta', 'Local Coleta', 'Latitude', 'Longitude', 'Altitude (m)', 'Sexo', 'Estagio', 'Imagem', 'Notas'],
    'template.example': ['EX-0001', 'Coleoptera', 'Coccinellidae', 'Coccinella septempunctata', '2025-03-14', 'Parque Estadual do Rio Doce', '-19.75', '-42.60', '250', 'fêmea', 'adulto', 'EX-0001.jpg', '']
  },

  en: {
    'file.collection_csv': 'entomobase_collection', 'file.project_csv': (p) => `project_${p.id}_specimens`,
    'file.full_suffix': '_full', 'file.collection_dwc': 'entomobase_darwincore',
    'file.project_dwc': (p) => `project_${p.id}_darwincore`, 'file.import_template': 'entomobase_import_template',
    'template.default_trait': 'Body length',
    'template.header': ['Catalog Number', 'Order', 'Family', 'Species', 'Collection Date', 'Locality', 'Latitude', 'Longitude', 'Elevation (m)', 'Sex', 'Life Stage', 'Image', 'Notes'],
    'template.example': ['EX-0001', 'Coleoptera', 'Coccinellidae', 'Coccinella septempunctata', '2025-03-14', 'Rio Doce State Park', '-19.75', '-42.60', '250', 'female', 'adult', 'EX-0001.jpg', '']
  }
};

// returns the message for key in lang, filling in params; falls back to Portuguese, then to the key itself
function translate(lang, key, params = {}) {
  const message = (MESSAGES[lang] || {})[key] ?? MESSAGES.pt[key];
  if (message === undefined) return key;
  return typeof message === 'function' ? message(params) : message;
}

// field name as shown to the user; nested fields like measurements.0.value become "Medida 1, valor"
function fieldLabel(lang, field) {
  if (!field) return '';
  const parts = field.split('.');
  if (parts[0] === 'measurements' && parts.length >= 2) {
    const label = translate(lang, 'field.measurement', { n: Number(parts[1]) + 1 });
    return parts[2] ? `${label}, ${translate(lang, `field.${parts[2]}`)}` : label;
  }
  const label = translate(lang, `field.${field}`);
  return label === `field.${field}` ? field : label;
}

function describeProblem(lang, problem) {
  return translate(lang, `problem.${problem.code}`, { ...(problem.params || {}), label: fieldLabel(lang, problem.field) });
}
