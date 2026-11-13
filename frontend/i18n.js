// every text the site shows, per language; app.js reads them through translate()
// a message is a string, a list, or a function that receives the params sent with it

const plural = (n, one, many) => (n === 1 ? one : many);

const MESSAGES = {
  pt: {
    // header, tabs and language switch
    'site.home_aria': 'EntomoBase, página inicial',
    'lang.toggle': 'EN', 'lang.toggle_aria': 'Ver o site em inglês',
    'search.label': 'Buscar', 'search.placeholder': 'espécie, projeto, local', 'search.aria': 'Buscar no site',
    'search.see_all': (p) => `Ver todos os ${p.n} resultados`,
    'search.nothing': (p) => `Nada encontrado para "${p.q}".`,
    'auth.login': 'Entrar', 'auth.logout': 'Sair',
    'nav.aria': 'Seções do site',
    'tab.about': 'Sobre', 'tab.projects': 'Projetos', 'tab.collection': 'Coleção', 'tab.members': 'Membros',
    'title.search': 'Busca', 'title.project': 'Projeto',

    // about page and contact; the bracketed texts are placeholders to fill in
    'about.text': '[Texto: o que é a EntomoBase, quem mantém, objetivo científico e como os dados são organizados.]',
    'about.team_name': '[Nome Sobrenome]', 'about.team_role': 'Graduando em Ciências Biológicas (UFMG)',
    'contact.value': '[e-mail de contato]',

    // counts: p.n is the formatted number, p.count the raw one
    'count.result': (p) => `${p.n} ${plural(p.count, 'resultado', 'resultados')}`,
    'count.project': (p) => `${p.n} ${plural(p.count, 'projeto', 'projetos')}`,
    'count.species': (p) => `${p.n} ${plural(p.count, 'espécie', 'espécies')}`,
    'count.specimen': (p) => `${p.n} ${plural(p.count, 'espécime', 'espécimes')}`,
    'count.family': (p) => `${p.n} ${plural(p.count, 'família', 'famílias')}`,
    'count.repository': (p) => `${p.n} ${plural(p.count, 'repositório', 'repositórios')}`,
    'count.point': (p) => `${p.n} ${plural(p.count, 'ponto', 'pontos')}`,
    'count.no_coordinates': (p) => `${p.n} ${plural(p.count, 'espécime sem coordenadas', 'espécimes sem coordenadas')}`,
    'count.with_image': (p) => `${p.n} com imagem`,
    'count.row': (p) => `${p.n} ${plural(p.count, 'linha', 'linhas')}`,
    'count.created': (p) => `${p.n} ${plural(p.count, 'espécime criado', 'espécimes criados')}`,
    'count.updated': (p) => `${p.n} ${plural(p.count, 'atualizado', 'atualizados')}`,
    'count.skipped': (p) => `${p.n} ${plural(p.count, 'ignorado', 'ignorados')}`,

    // search page
    'search.title': 'Busca',
    'search.min_chars': 'Digite pelo menos 2 letras para buscar em projetos, espécies, espécimes e repositórios.',
    'search.results_for': (p) => `${p.count} para "${p.q}"`,
    'search.projects': 'Projetos', 'search.species': 'Espécies', 'search.repositories': 'Repositórios',
    'search.specimens': 'Espécimes', 'search.pages': 'Páginas',
    'search.showing_30': (p) => `Mostrando 30 de ${p.n}. Refine a busca para ver os demais.`,
    'search.no_results': 'Nenhum resultado encontrado.',
    'search.try_other': 'Tente outro nome de espécie, projeto, local ou código de etiqueta.',
    'common.no_family': 'Sem família', 'common.no_description': 'Sem descrição.', 'common.no_locality': 'Local não informado',

    // API connection
    'api.offline': 'Sem conexão com a API.', 'api.check': (p) => `Verifique se o servidor está rodando em ${p.url}.`,
    'api.retry': 'Tentar de novo',
    'error.connection': 'Não foi possível conectar à API.',
    'error.session_expired_login': 'Sua sessão expirou. Entre novamente.', 'error.session_expired_short': 'Sessão expirada.',

    // project list
    'projects.title': 'Projetos', 'projects.new': 'Novo projeto', 'projects.loading': 'Carregando projetos...',
    'projects.none': 'Nenhum projeto encontrado.',
    'filter.year': 'Ano', 'filter.group': 'Grupo', 'filter.status': 'Status', 'filter.locality': 'Local',
    'filter.all': 'Todos', 'filter.sort': (p) => `Ordenar: ${p.label}`, 'filter.clear': 'Limpar filtros',
    'sort.recent': 'Mais recentes', 'sort.title': 'Título (A-Z)', 'sort.species': 'Mais espécies',
    'status.finished': 'Concluído', 'status.in_progress': 'Em andamento',

    // project page
    'project.loading': 'Carregando projeto...', 'project.not_found': 'Projeto não encontrado.',
    'project.see_all': 'Ver todos os projetos', 'project.specimens': 'Espécimes',
    'project.add_specimen': 'Adicionar espécime', 'project.no_specimens': 'Nenhum espécime cadastrado neste projeto.',
    'common.edit': 'Editar', 'common.delete': 'Excluir', 'common.cancel': 'Cancelar', 'common.close': 'Fechar',
    'common.save': 'Salvar', 'common.saving': 'Salvando...', 'common.no_data': 'Sem dados.',
    'fact.species': 'Espécies', 'fact.specimens': 'Espécimes', 'fact.with_image': 'Com imagem',
    'fact.traits': 'Traços medidos', 'fact.see_more': (p) => `+${p.n} ver mais`, 'fact.locality': 'Local de coleta',
    'fact.publication': 'Publicação', 'fact.open_publication': 'Abrir publicação', 'fact.repository': 'Repositório',
    'fact.no_repository': 'Sem repositório vinculado',
    'export.csv': 'Exportar CSV', 'export.csv_full_internal': 'CSV completo (interno)', 'export.csv_full': 'CSV completo',
    'export.csv_full_hint': 'Inclui coletor, localização física e empréstimo',
    'export.dwc': 'Darwin Core', 'export.dwc_hint': 'Pacote Darwin Core para GBIF',
    'view.aria': 'Modo de visualização', 'view.table': 'Tabela', 'view.gallery': 'Galeria', 'view.map': 'Mapa',
    'view.tree': 'Árvore', 'view.repos': 'Repositórios',

    // project table
    'table.search_label': 'Buscar nesta tabela', 'table.search_placeholder': 'Buscar neste projeto',
    'table.per_page': 'Linhas por página', 'table.image': 'Imagem', 'table.actions': 'Ações',
    'col.catalog': 'Etiqueta', 'col.species': 'Espécie', 'col.family': 'Família', 'col.locality': 'Local', 'col.date': 'Coleta',
    'table.details_aria': (p) => `Ver detalhes de ${p.code}`,
    'table.no_match': 'Nenhum espécime encontrado para essa busca.',
    'table.showing': (p) => `Mostrando ${p.range}`,
    'table.range': (p) => `${p.start} a ${p.end} de ${p.total}`, 'table.range_empty': '0 de 0',
    'table.pages_aria': 'Páginas da tabela', 'table.prev': 'Anterior', 'table.next': 'Próxima',

    // map and gallery
    'map.aria': 'Mapa de coleta',
    'map.unavailable': 'Não foi possível carregar o mapa (biblioteca Leaflet indisponível). Verifique a conexão com a internet.',
    'map.details': 'Ver detalhes',
    'gallery.details': (p) => `Ver detalhes de ${p.species}, ${p.code}`,
    'gallery.more': (p) => `Mostrar mais (${p.n} restantes)`,
    'photo.none': 'Sem imagem',

    // collection
    'collection.title': 'Coleção', 'collection.filters_aria': 'Filtros da coleção', 'collection.filter_title': 'Filtrar',
    'collection.hide_filters': 'Ocultar filtros', 'collection.show_filters': 'Mostrar filtros', 'collection.active': ' (ativos)',
    'collection.filter_label': 'Filtrar a coleção', 'collection.filter_placeholder': 'Filtrar a coleção',
    'collection.hosted': 'hospedados no Zenodo', 'collection.loading': 'Carregando coleção...',
    'collection.clear': 'Limpar filtros e busca',
    'facet.order': 'Ordem', 'facet.family': 'Família', 'facet.repository': 'Repositório', 'facet.year': 'Ano',
    'facet.no_repos': 'Nenhum repositório vinculado ainda.',
    'tree.expand': 'Expandir tudo', 'tree.collapse': 'Recolher tudo', 'tree.no_repo': 'Sem repositório',
    'tree.none': 'Nenhuma espécie encontrada.',
    'repos.none': 'Nenhum repositório encontrado.',
    'repos.hint': 'Adicione o link do Zenodo na edição de um projeto para que ele apareça aqui.',

    // footer, citation and contact
    'footer.license': 'Dados sob licença [CC BY 4.0]', 'footer.cite': 'Como citar', 'footer.contact': 'Contato',
    'cite.title': 'Como citar', 'cite.copy': 'Copiar citação',
    'cite.note': 'Ao usar dados de um projeto específico, cite também o repositório no Zenodo indicado na página do projeto.',
    'cite.text': (p) => `EntomoBase. Universidade Federal de Minas Gerais. Disponível em: ${p.url}. Acesso em: ${p.date}.`,
    'contact.title': 'Contato',

    // login
    'login.title': 'Entrar', 'login.email': 'E-mail', 'login.password': 'Senha',
    'login.submit': 'Acessar', 'login.submitting': 'Entrando...',
    'login.no_account': 'Ainda não tem conta?', 'login.to_signup': 'Cadastre-se',

    // sign-up and e-mail confirmation
    'signup.title': 'Criar conta', 'signup.name': 'Nome',
    'signup.password_hint': (p) => `Pelo menos ${p.minimum} caracteres.`,
    'signup.submit': 'Criar conta', 'signup.submitting': 'Enviando...',
    'signup.have_account': 'Já tem conta?', 'signup.to_login': 'Entrar',
    'signup.sent_title': 'Confira seu e-mail',
    'signup.sent_text': (p) => `Enviamos uma mensagem para ${p.email}. Abra o link dela para confirmar sua conta; ele vale por 24 horas. Se esse e-mail já tinha conta, a mensagem explica como entrar. Não chegou? Veja a caixa de spam ou cadastre-se de novo.`,
    'account.next_step': 'Para trabalhar em um laboratório, peça ao administrador dele que adicione você com esse e-mail.',
    'verify.title': 'Confirmação de e-mail',
    'verify.working': 'Confirmando seu e-mail...',
    'verify.done': (p) => `Pronto! O e-mail ${p.email} foi confirmado e você já pode entrar.`,
    'verify.no_code': 'Para confirmar sua conta, abra o link que enviamos por e-mail.',

    // home page
    'home.title': 'Coleções de insetos, abertas',
    'home.lead': 'Espécimes, fotos e medidas de laboratórios de pesquisa, num só lugar. Cada laboratório organiza sua coleção e escolhe o que mostrar ao público.',
    'home.explore': 'Explorar laboratórios',
    'home.stat_laboratories': (p) => plural(p.count, 'laboratório', 'laboratórios'),
    'home.stat_specimens': (p) => plural(p.count, 'espécime', 'espécimes'),
    'home.stat_species': (p) => plural(p.count, 'espécie', 'espécies'),
    'home.stat_projects': (p) => plural(p.count, 'projeto público', 'projetos públicos'),
    'home.your_labs': 'Seus laboratórios',
    'home.how_title': 'Como funciona',
    'home.step_account_title': 'Crie sua conta',
    'home.step_account_text': 'Com seu e-mail e uma senha. Um link de confirmação chega na sua caixa de entrada.',
    'home.step_join_title': 'Entre no laboratório',
    'home.step_join_text': 'Um administrador do laboratório adiciona você como pesquisador(a) ou administrador(a).',
    'home.step_record_title': 'Cadastre os espécimes',
    'home.step_record_text': 'Um a um ou importando uma planilha CSV. Os nomes científicos são conferidos no GBIF.',
    'home.step_publish_title': 'Publique quando quiser',
    'home.step_publish_text': 'Cada projeto é privado, só com link ou público. Os dados públicos saem em CSV e Darwin Core e podem ir para o Zenodo.',
    'home.have_account': 'Já tenho conta',

    // laboratories
    'labs.title': 'Laboratórios', 'labs.all': 'Laboratórios',
    'labs.subtitle': 'Laboratórios que publicam seus dados no EntomoBase.',
    'labs.loading': 'Carregando laboratórios...',
    'labs.empty': 'Ainda não há laboratórios públicos.',
    'labs.bar_aria': 'Laboratório',

    // a project opened by its share link
    'shared.title': 'Projeto compartilhado',
    'shared.note': (p) => `Projeto de ${p.lab}, compartilhado por link. Ele não é público: só quem recebeu o link pode vê-lo.`,
    'shared.specimens': (p) => `Espécimes (${p.n})`,
    'shared.no_specimens': 'Este projeto ainda não tem espécimes.',
    'shared.gone': 'O link pode estar incompleto ou ter sido desativado pelo laboratório.',

    // laboratory members
    'members.title': 'Membros do laboratório',
    'members.login_needed': 'Entre para gerenciar os membros do seu laboratório.',
    'members.not_admin': 'Só os administradores de um laboratório veem e gerenciam os membros dele.',
    'members.lab': 'Laboratório',
    'members.add_title': 'Adicionar membro', 'members.role': 'Papel',
    'members.add': 'Adicionar', 'members.adding': 'Adicionando...',
    'members.add_hint': 'A pessoa precisa já ter criado a conta e confirmado o e-mail.',
    'members.list_title': (p) => `Membros (${p.n})`,
    'members.loading': 'Carregando membros...',
    'members.you': 'você',
    'members.role_aria': (p) => `Papel de ${p.email}`,
    'members.remove': 'Remover', 'members.removing': 'Removendo...',
    'members.remove_aria': (p) => `Remover ${p.email}`,
    'members.remove_title': 'Remover membro',
    'members.remove_text': (p) => `${p.email} perderá o acesso ao que é privado neste laboratório. A conta e o que a pessoa já cadastrou continuam.`,
    'members.remove_self_text': 'Você perderá o acesso ao que é privado neste laboratório.',
    'role.admin': 'Administrador(a)', 'role.researcher': 'Pesquisador(a)',
    'notify.member_added': (p) => `${p.email} agora é membro do laboratório.`,
    'notify.member_removed': 'Membro removido.', 'notify.role_changed': 'Papel atualizado.',
    'notify.left_admin': 'Você não administra mais esse laboratório.',

    // project form
    'projectForm.new': 'Novo projeto', 'projectForm.edit': 'Editar projeto',
    'projectForm.title': 'Título', 'projectForm.year': 'Ano', 'projectForm.group': 'Grupo de insetos',
    'projectForm.locality': 'Local de coleta', 'projectForm.traits': 'Traços medidos', 'projectForm.description': 'Descrição',
    'projectForm.dataset': 'Link do repositório (Zenodo)', 'projectForm.publication': 'Publicação vinculada (link ou referência)',
    'projectForm.cover': 'URL da imagem de capa', 'projectForm.finished': 'Projeto concluído (a pesquisa terminou)',
    'projectForm.visibility': 'Quem pode ver', 'visibility.private': 'Privado (só o laboratório)',
    'visibility.unlisted': 'Só com o link', 'visibility.public': 'Público',
    'visibility.hint_private': 'Só os membros do laboratório veem.',
    'visibility.hint_unlisted': 'Quem tiver o link vê, sem precisar entrar. O projeto não aparece nas listas, na busca nem nas exportações públicas. Mudar para outra opção desativa o link.',
    'visibility.hint_public': 'Qualquer pessoa vê. O projeto aparece nas listas, na busca e nas exportações públicas.',
    'badge.private': 'Privado', 'badge.unlisted': 'Só com link', 'badge.public': 'Público',
    'share.title': 'Link de compartilhamento.', 'share.text': 'Quem tiver este link vê o projeto e os espécimes, sem os campos internos.',
    'share.copy': 'Copiar link', 'notify.share_copied': 'Link copiado.',

    // specimen form
    'specimenForm.new': 'Novo espécime', 'specimenForm.edit': 'Editar espécime',
    'sf.catalog': 'Código da etiqueta', 'sf.project': 'Projeto', 'sf.none': 'Nenhum',
    'sf.order': 'Ordem', 'sf.family': 'Família', 'sf.species': 'Espécie',
    'sf.date': 'Data da coleta', 'sf.locality': 'Local de coleta', 'sf.latitude': 'Latitude', 'sf.longitude': 'Longitude',
    'sf.elevation': 'Altitude (m)', 'sf.sex': 'Sexo', 'sf.stage': 'Estágio',
    'sf.id_legend': 'Identificação e coleta (público)', 'sf.identified_by': 'Determinador',
    'sf.id_date': 'Data da determinação', 'sf.method': 'Método de coleta', 'sf.method_placeholder': 'armadilha, rede entomológica...',
    'sf.habitat': 'Habitat', 'sf.measurements': 'Medidas', 'sf.trait': 'Traço', 'sf.trait_aria': 'Nome do traço',
    'sf.value': 'Valor', 'sf.unit_aria': 'Unidade', 'sf.remove': 'Remover', 'sf.add_measurement': 'Adicionar medida',
    'sf.image_file': 'Arquivo da imagem no repositório do projeto', 'sf.image_placeholder': 'ex.: RDO-0001.jpg',
    'sf.photo_url': 'URL da fotografia (opcional, substitui o repositório)', 'sf.notes': 'Notas (públicas)',
    'sf.internal_legend': 'Acervo interno (não aparece para visitantes)', 'sf.collector': 'Coletor',
    'sf.field_number': 'Número de campo', 'sf.storage': 'Localização física', 'sf.storage_placeholder': 'ex.: Armário 2, caixa 14',
    'sf.loan_status': 'Situação', 'sf.loan_placeholder': 'no acervo, emprestado...', 'sf.loaned_to': 'Emprestado para',
    'sf.loan_date': 'Data do empréstimo', 'sf.internal_notes': 'Notas internas',
    'sf.trait_required': 'Dê um nome ao traço de cada medida preenchida.',
    'gbif.not_found': (p) => `O GBIF não reconhece "${p.name}". Confira a grafia.`,
    'gbif.genus_only': 'O GBIF só reconheceu o gênero', 'gbif.synonym': (p) => `No GBIF, "${p.name}" é sinônimo de`,
    'gbif.fuzzy': 'No GBIF, a grafia aceita parece ser', 'gbif.use': 'Usar este nome',

    // specimen panel
    'panel.close': 'Fechar', 'panel.no_image': 'Imagem não disponível', 'panel.prev': 'Anterior', 'panel.next': 'Próximo',
    'panel.collected': 'Coleta', 'panel.locality': 'Local', 'panel.coordinates': 'Coordenadas', 'panel.elevation': 'Altitude',
    'panel.file': 'Arquivo', 'panel.measurements': 'Medidas', 'panel.internal': 'Interno do laboratório',
    'panel.zenodo_file': 'Arquivo original no Zenodo', 'panel.repository': 'Repositório', 'panel.show_on_map': 'Ver no mapa',

    // CSV import
    'import.button': 'Importar CSV', 'import.title': 'Importar espécimes de um CSV', 'import.target': 'Projeto de destino',
    'import.by_column': 'Definido pela coluna do CSV', 'import.file': 'Arquivo CSV', 'import.template': 'Baixar modelo de CSV',
    'import.help': 'Aceita vírgula, ponto e vírgula ou tab. Colunas de medidas no formato "Traço (unidade)" são reconhecidas automaticamente. O arquivo exportado pelo site pode ser reimportado.',
    'import.columns_of': (p) => `Colunas de ${p.file}`, 'import.column': 'Coluna', 'import.example': 'Exemplo',
    'import.target_column': 'Destino', 'import.ignore': 'Ignorar', 'import.measurement': 'Medida',
    'import.target_aria': (p) => `Destino da coluna ${p.header}`,
    'import.defaults': 'Valores padrão (usados quando a coluna não existe ou a célula está vazia)',
    'import.if_exists': 'Se o código da etiqueta já existir:', 'import.skip_row': 'Ignorar a linha',
    'import.update': 'Atualizar o espécime', 'import.preview': 'Prévia', 'import.checking': 'Verificando...',
    'import.new': 'novos', 'import.updated': 'atualizados', 'import.skipped': 'ignorados', 'import.with_error': 'com erro',
    'import.line': (p) => `Linha ${p.n}`, 'import.first_12': 'Mostrando os 12 primeiros erros.',
    'import.names_title': 'Nomes para conferir no GBIF (não impedem a importação)',
    'import.apply_all': 'Aplicar todas as sugestões', 'import.use_suggestion': 'Usar sugestão',
    'import.gbif_down': (p) => `O GBIF não respondeu; ${p.rows} sem conferência de nome.`,
    'import.no_valid': 'Nenhuma linha válida para importar ainda.',
    'import.submit': 'Importar', 'import.importing': 'Importando...',
    'import.done': (p) => `Importação concluída: ${p.parts}.`, 'import.nothing_new': 'nada novo',
    'import.need_rows': 'O arquivo precisa ter uma linha de cabeçalho e pelo menos uma linha de dados.',
    'import.too_many': 'O arquivo tem mais de 5.000 linhas. Divida em partes menores.',
    'warning.fuzzy': 'Nome aproximado', 'warning.synonym': 'Sinônimo',
    'warning.genus_only': 'Só o gênero foi reconhecido', 'warning.not_found': 'Não encontrado no GBIF',
    'importField.catalog_number': 'Código da etiqueta', 'importField.insect_order': 'Ordem', 'importField.family': 'Família',
    'importField.species': 'Espécie', 'importField.collection_date': 'Data da coleta', 'importField.locality': 'Local de coleta',
    'importField.latitude': 'Latitude', 'importField.longitude': 'Longitude', 'importField.elevation_m': 'Altitude (m)',
    'importField.sex': 'Sexo', 'importField.life_stage': 'Estágio', 'importField.image_file': 'Arquivo da imagem',
    'importField.photo_url': 'URL da fotografia', 'importField.notes': 'Notas', 'importField.project': 'Projeto (título)',
    'importField.project_id': 'Projeto (id)', 'importField.identified_by': 'Determinador',
    'importField.identification_date': 'Data da determinação', 'importField.sampling_method': 'Método de coleta',
    'importField.habitat': 'Habitat', 'importField.collector': 'Coletor (interno)',
    'importField.field_number': 'Número de campo (interno)', 'importField.storage_location': 'Localização física (interno)',
    'importField.loan_status': 'Empréstimo (interno)', 'importField.loaned_to': 'Emprestado para (interno)',
    'importField.loan_date': 'Data do empréstimo (interno)', 'importField.internal_notes': 'Notas internas',

    // confirmations and notices
    'confirm.deleting': 'Excluindo...',
    'confirm.project_title': 'Excluir projeto',
    'confirm.project_text': (p) => `"${p.title}" será excluído${p.with ? ` junto com ${p.with}` : ''}. Essa ação não pode ser desfeita.`,
    'confirm.specimen_title': 'Excluir espécime',
    'confirm.specimen_text': (p) => `O espécime ${p.code} (${p.species}) será excluído. Essa ação não pode ser desfeita.`,
    'notify.project_updated': 'Projeto atualizado.', 'notify.project_created': 'Projeto criado.',
    'notify.project_deleted': 'Projeto excluído.', 'notify.specimen_updated': 'Espécime atualizado.',
    'notify.specimen_added': 'Espécime adicionado.', 'notify.specimen_deleted': 'Espécime excluído.',
    'notify.citation_copied': 'Citação copiada.',
    'notify.copy_failed': 'Não foi possível copiar. Selecione o texto e copie manualmente.',

    // errors sent by the API as {"code": ..., "params": ...}
    'error.missing_token': 'Token ausente ou inválido',
    'error.forbidden': 'Você não tem permissão para fazer isso neste laboratório.',
    'error.lab_not_found': 'Laboratório não encontrado.',
    'error.duplicate_slug': 'Já existe um laboratório com esse endereço.',
    'error.user_not_found': 'Usuário não encontrado.',
    'error.member_not_found': 'Membro não encontrado.',
    'error.last_admin': 'O laboratório precisa ter pelo menos um administrador.',
    'error.already_member': 'Essa pessoa já é membro do laboratório.',
    'error.invalid_email': 'Informe um e-mail válido.',
    'error.weak_password': (p) => `A senha precisa ter pelo menos ${p.minimum} caracteres.`,
    'error.mail_unavailable': 'Não foi possível enviar o e-mail agora. Tente novamente mais tarde.',
    'error.email_not_confirmed': 'Confirme seu e-mail antes de entrar. Para receber um novo link, cadastre-se de novo com o mesmo e-mail.',
    'error.invalid_code': 'Este link de confirmação é inválido ou expirou. Cadastre-se de novo para receber outro.',
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
    'site.home_aria': 'EntomoBase, home page',
    'lang.toggle': 'PT', 'lang.toggle_aria': 'View the site in Portuguese',
    'search.label': 'Search', 'search.placeholder': 'species, project, locality', 'search.aria': 'Search the site',
    'search.see_all': (p) => `See all ${p.n} results`,
    'search.nothing': (p) => `Nothing found for "${p.q}".`,
    'auth.login': 'Sign in', 'auth.logout': 'Sign out',
    'nav.aria': 'Site sections',
    'tab.about': 'About', 'tab.projects': 'Projects', 'tab.collection': 'Collection', 'tab.members': 'Members',
    'title.search': 'Search', 'title.project': 'Project',

    'about.text': '[Text: what EntomoBase is, who maintains it, its scientific goal and how the data is organized.]',
    'about.team_name': '[First Last]', 'about.team_role': 'Biological Sciences undergraduate (UFMG)',
    'contact.value': '[contact e-mail]',

    'count.result': (p) => `${p.n} ${plural(p.count, 'result', 'results')}`,
    'count.project': (p) => `${p.n} ${plural(p.count, 'project', 'projects')}`,
    'count.species': (p) => `${p.n} species`,
    'count.specimen': (p) => `${p.n} ${plural(p.count, 'specimen', 'specimens')}`,
    'count.family': (p) => `${p.n} ${plural(p.count, 'family', 'families')}`,
    'count.repository': (p) => `${p.n} ${plural(p.count, 'repository', 'repositories')}`,
    'count.point': (p) => `${p.n} ${plural(p.count, 'point', 'points')}`,
    'count.no_coordinates': (p) => `${p.n} ${plural(p.count, 'specimen without coordinates', 'specimens without coordinates')}`,
    'count.with_image': (p) => `${p.n} with an image`,
    'count.row': (p) => `${p.n} ${plural(p.count, 'row', 'rows')}`,
    'count.created': (p) => `${p.n} ${plural(p.count, 'specimen created', 'specimens created')}`,
    'count.updated': (p) => `${p.n} updated`,
    'count.skipped': (p) => `${p.n} skipped`,

    'search.title': 'Search',
    'search.min_chars': 'Type at least 2 letters to search projects, species, specimens and repositories.',
    'search.results_for': (p) => `${p.count} for "${p.q}"`,
    'search.projects': 'Projects', 'search.species': 'Species', 'search.repositories': 'Repositories',
    'search.specimens': 'Specimens', 'search.pages': 'Pages',
    'search.showing_30': (p) => `Showing 30 of ${p.n}. Refine the search to see the rest.`,
    'search.no_results': 'No results found.',
    'search.try_other': 'Try another species, project, locality or catalog number.',
    'common.no_family': 'No family', 'common.no_description': 'No description.', 'common.no_locality': 'Locality not given',

    'api.offline': 'No connection to the API.', 'api.check': (p) => `Check that the server is running at ${p.url}.`,
    'api.retry': 'Try again',
    'error.connection': 'Could not connect to the API.',
    'error.session_expired_login': 'Your session expired. Sign in again.', 'error.session_expired_short': 'Session expired.',

    'projects.title': 'Projects', 'projects.new': 'New project', 'projects.loading': 'Loading projects...',
    'projects.none': 'No projects found.',
    'filter.year': 'Year', 'filter.group': 'Group', 'filter.status': 'Status', 'filter.locality': 'Locality',
    'filter.all': 'All', 'filter.sort': (p) => `Sort: ${p.label}`, 'filter.clear': 'Clear filters',
    'sort.recent': 'Most recent', 'sort.title': 'Title (A-Z)', 'sort.species': 'Most species',
    'status.finished': 'Finished', 'status.in_progress': 'In progress',

    'project.loading': 'Loading project...', 'project.not_found': 'Project not found.',
    'project.see_all': 'See all projects', 'project.specimens': 'Specimens',
    'project.add_specimen': 'Add specimen', 'project.no_specimens': 'No specimens in this project yet.',
    'common.edit': 'Edit', 'common.delete': 'Delete', 'common.cancel': 'Cancel', 'common.close': 'Close',
    'common.save': 'Save', 'common.saving': 'Saving...', 'common.no_data': 'No data.',
    'fact.species': 'Species', 'fact.specimens': 'Specimens', 'fact.with_image': 'With image',
    'fact.traits': 'Measured traits', 'fact.see_more': (p) => `+${p.n} more`, 'fact.locality': 'Collection locality',
    'fact.publication': 'Publication', 'fact.open_publication': 'Open publication', 'fact.repository': 'Repository',
    'fact.no_repository': 'No linked repository',
    'export.csv': 'Export CSV', 'export.csv_full_internal': 'Full CSV (internal)', 'export.csv_full': 'Full CSV',
    'export.csv_full_hint': 'Includes collector, storage location and loan',
    'export.dwc': 'Darwin Core', 'export.dwc_hint': 'Darwin Core archive for GBIF',
    'view.aria': 'View mode', 'view.table': 'Table', 'view.gallery': 'Gallery', 'view.map': 'Map',
    'view.tree': 'Tree', 'view.repos': 'Repositories',

    'table.search_label': 'Search this table', 'table.search_placeholder': 'Search this project',
    'table.per_page': 'Rows per page', 'table.image': 'Image', 'table.actions': 'Actions',
    'col.catalog': 'Catalog no.', 'col.species': 'Species', 'col.family': 'Family', 'col.locality': 'Locality', 'col.date': 'Collected',
    'table.details_aria': (p) => `View details of ${p.code}`,
    'table.no_match': 'No specimens match this search.',
    'table.showing': (p) => `Showing ${p.range}`,
    'table.range': (p) => `${p.start} to ${p.end} of ${p.total}`, 'table.range_empty': '0 of 0',
    'table.pages_aria': 'Table pages', 'table.prev': 'Previous', 'table.next': 'Next',

    'map.aria': 'Collection map',
    'map.unavailable': 'Could not load the map (Leaflet library unavailable). Check the internet connection.',
    'map.details': 'View details',
    'gallery.details': (p) => `View details of ${p.species}, ${p.code}`,
    'gallery.more': (p) => `Show more (${p.n} left)`,
    'photo.none': 'No image',

    'collection.title': 'Collection', 'collection.filters_aria': 'Collection filters', 'collection.filter_title': 'Filter',
    'collection.hide_filters': 'Hide filters', 'collection.show_filters': 'Show filters', 'collection.active': ' (active)',
    'collection.filter_label': 'Filter the collection', 'collection.filter_placeholder': 'Filter the collection',
    'collection.hosted': 'hosted on Zenodo', 'collection.loading': 'Loading collection...',
    'collection.clear': 'Clear filters and search',
    'facet.order': 'Order', 'facet.family': 'Family', 'facet.repository': 'Repository', 'facet.year': 'Year',
    'facet.no_repos': 'No linked repositories yet.',
    'tree.expand': 'Expand all', 'tree.collapse': 'Collapse all', 'tree.no_repo': 'No repository',
    'tree.none': 'No species found.',
    'repos.none': 'No repositories found.',
    'repos.hint': 'Add the Zenodo link when editing a project to list it here.',

    'footer.license': 'Data under the [CC BY 4.0] license', 'footer.cite': 'How to cite', 'footer.contact': 'Contact',
    'cite.title': 'How to cite', 'cite.copy': 'Copy citation',
    'cite.note': 'When using data from a specific project, also cite the Zenodo repository shown on the project page.',
    'cite.text': (p) => `EntomoBase. Federal University of Minas Gerais. Available at: ${p.url}. Accessed on: ${p.date}.`,
    'contact.title': 'Contact',

    'login.title': 'Sign in', 'login.email': 'E-mail', 'login.password': 'Password',
    'login.submit': 'Sign in', 'login.submitting': 'Signing in...',
    'login.no_account': 'No account yet?', 'login.to_signup': 'Sign up',

    'signup.title': 'Create an account', 'signup.name': 'Name',
    'signup.password_hint': (p) => `At least ${p.minimum} characters.`,
    'signup.submit': 'Create account', 'signup.submitting': 'Sending...',
    'signup.have_account': 'Already have an account?', 'signup.to_login': 'Sign in',
    'signup.sent_title': 'Check your e-mail',
    'signup.sent_text': (p) => `We sent a message to ${p.email}. Open its link to confirm your account; it is valid for 24 hours. If this e-mail already had an account, the message explains how to sign in. Nothing arrived? Check the spam folder or sign up again.`,
    'account.next_step': 'To work in a laboratory, ask its admin to add you with this e-mail.',
    'verify.title': 'E-mail confirmation',
    'verify.working': 'Confirming your e-mail...',
    'verify.done': (p) => `Done! The e-mail ${p.email} is confirmed and you can sign in now.`,
    'verify.no_code': 'To confirm your account, open the link we sent you by e-mail.',

    'home.title': 'Insect collections, in the open',
    'home.lead': 'Specimens, photos and measurements from research laboratories, in one place. Each laboratory keeps its collection here and chooses what to show the public.',
    'home.explore': 'Explore laboratories',
    'home.stat_laboratories': (p) => plural(p.count, 'laboratory', 'laboratories'),
    'home.stat_specimens': (p) => plural(p.count, 'specimen', 'specimens'),
    'home.stat_species': () => 'species',
    'home.stat_projects': (p) => plural(p.count, 'public project', 'public projects'),
    'home.your_labs': 'Your laboratories',
    'home.how_title': 'How it works',
    'home.step_account_title': 'Create an account',
    'home.step_account_text': 'With your e-mail and a password. A confirmation link arrives in your inbox.',
    'home.step_join_title': 'Join the laboratory',
    'home.step_join_text': 'An admin of the laboratory adds you as a researcher or an admin.',
    'home.step_record_title': 'Record the specimens',
    'home.step_record_text': 'One by one or by importing a CSV spreadsheet. Scientific names are checked against GBIF.',
    'home.step_publish_title': 'Publish when ready',
    'home.step_publish_text': 'Each project is private, link-only or public. Public data comes out as CSV and Darwin Core and can go to Zenodo.',
    'home.have_account': 'I already have an account',

    'labs.title': 'Laboratories', 'labs.all': 'Laboratories',
    'labs.subtitle': 'Laboratories that publish their data on EntomoBase.',
    'labs.loading': 'Loading laboratories...',
    'labs.empty': 'There are no public laboratories yet.',
    'labs.bar_aria': 'Laboratory',

    'shared.title': 'Shared project',
    'shared.note': (p) => `A project by ${p.lab}, shared by link. It is not public: only people who received the link can see it.`,
    'shared.specimens': (p) => `Specimens (${p.n})`,
    'shared.no_specimens': 'This project has no specimens yet.',
    'shared.gone': 'The link may be incomplete or may have been turned off by the laboratory.',

    'members.title': 'Laboratory members',
    'members.login_needed': 'Sign in to manage the members of your laboratory.',
    'members.not_admin': 'Only the admins of a laboratory can see and manage its members.',
    'members.lab': 'Laboratory',
    'members.add_title': 'Add a member', 'members.role': 'Role',
    'members.add': 'Add', 'members.adding': 'Adding...',
    'members.add_hint': 'The person must already have created an account and confirmed the e-mail.',
    'members.list_title': (p) => `Members (${p.n})`,
    'members.loading': 'Loading members...',
    'members.you': 'you',
    'members.role_aria': (p) => `Role of ${p.email}`,
    'members.remove': 'Remove', 'members.removing': 'Removing...',
    'members.remove_aria': (p) => `Remove ${p.email}`,
    'members.remove_title': 'Remove member',
    'members.remove_text': (p) => `${p.email} will lose access to what is private in this laboratory. The account and what they already added stay.`,
    'members.remove_self_text': 'You will lose access to what is private in this laboratory.',
    'role.admin': 'Admin', 'role.researcher': 'Researcher',
    'notify.member_added': (p) => `${p.email} is now a member of the laboratory.`,
    'notify.member_removed': 'Member removed.', 'notify.role_changed': 'Role updated.',
    'notify.left_admin': 'You no longer manage that laboratory.',

    'projectForm.new': 'New project', 'projectForm.edit': 'Edit project',
    'projectForm.title': 'Title', 'projectForm.year': 'Year', 'projectForm.group': 'Insect group',
    'projectForm.locality': 'Collection locality', 'projectForm.traits': 'Measured traits', 'projectForm.description': 'Description',
    'projectForm.dataset': 'Repository link (Zenodo)', 'projectForm.publication': 'Linked publication (link or reference)',
    'projectForm.cover': 'Cover image URL', 'projectForm.finished': 'Finished project (the research is done)',
    'projectForm.visibility': 'Who can see it', 'visibility.private': 'Private (only the laboratory)',
    'visibility.unlisted': 'Only with the link', 'visibility.public': 'Public',
    'visibility.hint_private': 'Only the members of the laboratory can see it.',
    'visibility.hint_unlisted': 'Anyone with the link can see it without signing in. The project stays out of the lists, the search and the public exports. Choosing another option turns the link off.',
    'visibility.hint_public': 'Anyone can see it. The project shows in the lists, the search and the public exports.',
    'badge.private': 'Private', 'badge.unlisted': 'Link only', 'badge.public': 'Public',
    'share.title': 'Share link.', 'share.text': 'Anyone with this link sees the project and its specimens, without the internal fields.',
    'share.copy': 'Copy link', 'notify.share_copied': 'Link copied.',

    'specimenForm.new': 'New specimen', 'specimenForm.edit': 'Edit specimen',
    'sf.catalog': 'Catalog number', 'sf.project': 'Project', 'sf.none': 'None',
    'sf.order': 'Order', 'sf.family': 'Family', 'sf.species': 'Species',
    'sf.date': 'Collection date', 'sf.locality': 'Collection locality', 'sf.latitude': 'Latitude', 'sf.longitude': 'Longitude',
    'sf.elevation': 'Elevation (m)', 'sf.sex': 'Sex', 'sf.stage': 'Life stage',
    'sf.id_legend': 'Identification and collection (public)', 'sf.identified_by': 'Identified by',
    'sf.id_date': 'Identification date', 'sf.method': 'Sampling method', 'sf.method_placeholder': 'trap, insect net...',
    'sf.habitat': 'Habitat', 'sf.measurements': 'Measurements', 'sf.trait': 'Trait', 'sf.trait_aria': 'Trait name',
    'sf.value': 'Value', 'sf.unit_aria': 'Unit', 'sf.remove': 'Remove', 'sf.add_measurement': 'Add measurement',
    'sf.image_file': 'Image file in the project repository', 'sf.image_placeholder': 'e.g. RDO-0001.jpg',
    'sf.photo_url': 'Photo URL (optional, replaces the repository)', 'sf.notes': 'Notes (public)',
    'sf.internal_legend': 'Internal collection data (hidden from visitors)', 'sf.collector': 'Collector',
    'sf.field_number': 'Field number', 'sf.storage': 'Storage location', 'sf.storage_placeholder': 'e.g. Cabinet 2, box 14',
    'sf.loan_status': 'Status', 'sf.loan_placeholder': 'in collection, on loan...', 'sf.loaned_to': 'Loaned to',
    'sf.loan_date': 'Loan date', 'sf.internal_notes': 'Internal notes',
    'sf.trait_required': 'Name the trait of every filled-in measurement.',
    'gbif.not_found': (p) => `GBIF does not recognize "${p.name}". Check the spelling.`,
    'gbif.genus_only': 'GBIF only recognized the genus', 'gbif.synonym': (p) => `On GBIF, "${p.name}" is a synonym of`,
    'gbif.fuzzy': 'On GBIF, the accepted spelling seems to be', 'gbif.use': 'Use this name',

    'panel.close': 'Close', 'panel.no_image': 'Image not available', 'panel.prev': 'Previous', 'panel.next': 'Next',
    'panel.collected': 'Collected', 'panel.locality': 'Locality', 'panel.coordinates': 'Coordinates', 'panel.elevation': 'Elevation',
    'panel.file': 'File', 'panel.measurements': 'Measurements', 'panel.internal': 'Lab internal',
    'panel.zenodo_file': 'Original file on Zenodo', 'panel.repository': 'Repository', 'panel.show_on_map': 'Show on map',

    'import.button': 'Import CSV', 'import.title': 'Import specimens from a CSV', 'import.target': 'Target project',
    'import.by_column': 'Set by the CSV column', 'import.file': 'CSV file', 'import.template': 'Download CSV template',
    'import.help': 'Accepts comma, semicolon or tab. Measurement columns named "Trait (unit)" are recognized automatically. Files exported by the site can be imported back.',
    'import.columns_of': (p) => `Columns of ${p.file}`, 'import.column': 'Column', 'import.example': 'Example',
    'import.target_column': 'Target', 'import.ignore': 'Ignore', 'import.measurement': 'Measurement',
    'import.target_aria': (p) => `Target of column ${p.header}`,
    'import.defaults': 'Default values (used when the column is missing or the cell is empty)',
    'import.if_exists': 'If the catalog number already exists:', 'import.skip_row': 'Skip the row',
    'import.update': 'Update the specimen', 'import.preview': 'Preview', 'import.checking': 'Checking...',
    'import.new': 'new', 'import.updated': 'updated', 'import.skipped': 'skipped', 'import.with_error': 'with errors',
    'import.line': (p) => `Row ${p.n}`, 'import.first_12': 'Showing the first 12 errors.',
    'import.names_title': 'Names to check on GBIF (they do not block the import)',
    'import.apply_all': 'Apply all suggestions', 'import.use_suggestion': 'Use suggestion',
    'import.gbif_down': (p) => `GBIF did not answer; ${p.rows} without a name check.`,
    'import.no_valid': 'No valid rows to import yet.',
    'import.submit': 'Import', 'import.importing': 'Importing...',
    'import.done': (p) => `Import finished: ${p.parts}.`, 'import.nothing_new': 'nothing new',
    'import.need_rows': 'The file needs a header row and at least one data row.',
    'import.too_many': 'The file has more than 5,000 rows. Split it into smaller parts.',
    'warning.fuzzy': 'Approximate name', 'warning.synonym': 'Synonym',
    'warning.genus_only': 'Only the genus was recognized', 'warning.not_found': 'Not found on GBIF',
    'importField.catalog_number': 'Catalog number', 'importField.insect_order': 'Order', 'importField.family': 'Family',
    'importField.species': 'Species', 'importField.collection_date': 'Collection date', 'importField.locality': 'Collection locality',
    'importField.latitude': 'Latitude', 'importField.longitude': 'Longitude', 'importField.elevation_m': 'Elevation (m)',
    'importField.sex': 'Sex', 'importField.life_stage': 'Life stage', 'importField.image_file': 'Image file',
    'importField.photo_url': 'Photo URL', 'importField.notes': 'Notes', 'importField.project': 'Project (title)',
    'importField.project_id': 'Project (id)', 'importField.identified_by': 'Identified by',
    'importField.identification_date': 'Identification date', 'importField.sampling_method': 'Sampling method',
    'importField.habitat': 'Habitat', 'importField.collector': 'Collector (internal)',
    'importField.field_number': 'Field number (internal)', 'importField.storage_location': 'Storage location (internal)',
    'importField.loan_status': 'Loan (internal)', 'importField.loaned_to': 'Loaned to (internal)',
    'importField.loan_date': 'Loan date (internal)', 'importField.internal_notes': 'Internal notes',

    'confirm.deleting': 'Deleting...',
    'confirm.project_title': 'Delete project',
    'confirm.project_text': (p) => `"${p.title}" will be deleted${p.with ? ` along with ${p.with}` : ''}. This cannot be undone.`,
    'confirm.specimen_title': 'Delete specimen',
    'confirm.specimen_text': (p) => `Specimen ${p.code} (${p.species}) will be deleted. This cannot be undone.`,
    'notify.project_updated': 'Project updated.', 'notify.project_created': 'Project created.',
    'notify.project_deleted': 'Project deleted.', 'notify.specimen_updated': 'Specimen updated.',
    'notify.specimen_added': 'Specimen added.', 'notify.specimen_deleted': 'Specimen deleted.',
    'notify.citation_copied': 'Citation copied.',
    'notify.copy_failed': 'Could not copy. Select the text and copy it manually.',

    'error.missing_token': 'Missing or invalid token',
    'error.forbidden': 'You do not have permission to do this in this laboratory.',
    'error.lab_not_found': 'Laboratory not found.',
    'error.duplicate_slug': 'A laboratory with this address already exists.',
    'error.user_not_found': 'User not found.',
    'error.member_not_found': 'Member not found.',
    'error.last_admin': 'The laboratory must keep at least one admin.',
    'error.already_member': 'This person is already a member of the laboratory.',
    'error.invalid_email': 'Enter a valid e-mail.',
    'error.weak_password': (p) => `The password must have at least ${p.minimum} characters.`,
    'error.mail_unavailable': 'The e-mail could not be sent right now. Please try again later.',
    'error.email_not_confirmed': 'Confirm your e-mail before signing in. To get a new link, sign up again with the same e-mail.',
    'error.invalid_code': 'This confirmation link is invalid or has expired. Sign up again to get a new one.',
    'error.session_expired': 'Session expired. Please sign in again.',
    'error.invalid_credentials': 'Wrong e-mail or password',
    'error.too_many_attempts': (p) => `Too many attempts. Try again in ${p.minutes} ${plural(p.minutes, 'minute', 'minutes')}.`,
    'error.project_not_found': 'Project not found',
    'error.specimen_not_found': 'Specimen not found.',
    'error.duplicate_catalog_number': 'This catalog number already exists.',
    'error.import_has_errors': (p) => `${p.count} row(s) with errors; nothing was imported.`,
    'error.full_csv_requires_login': 'The full CSV requires signing in.',
    'error.image_not_found': 'Image not found',
    'error.unknown': (p) => `Error ${p.status}`,

    'problem.required': (p) => `${p.label}: required`,
    'problem.empty': (p) => `${p.label}: cannot be empty`,
    'problem.max': (p) => `${p.label}: must be at most ${p.limit}`,
    'problem.min': (p) => `${p.label}: must be at least ${p.limit}`,
    'problem.invalid_value': (p) => (p.value !== undefined ? `${p.label}: invalid value (${p.value})` : `${p.label}: invalid value`),
    'problem.invalid_measurement': (p) => `invalid value in "${p.trait}": ${p.value}`,
    'problem.unknown_project': (p) => `project_id ${p.project_id} does not exist`,
    'problem.duplicate_in_file': (p) => `catalog number repeated in the file (first seen on row ${p.first_line})`,
    'problem.project_title_not_found': (p) => `project "${p.title}" not found`,
    'problem.invalid_project_id': (p) => `invalid project_id (${p.value})`,

    'field.catalog_number': 'Catalog number', 'field.insect_order': 'Order', 'field.family': 'Family',
    'field.species': 'Species', 'field.collection_date': 'Collection date', 'field.locality': 'Collection locality',
    'field.latitude': 'Latitude', 'field.longitude': 'Longitude', 'field.elevation_m': 'Elevation (m)',
    'field.sex': 'Sex', 'field.life_stage': 'Life stage', 'field.image_file': 'Image file',
    'field.photo_url': 'Photo URL', 'field.notes': 'Notes', 'field.project_id': 'Project',
    'field.identified_by': 'Identified by', 'field.identification_date': 'Identification date',
    'field.sampling_method': 'Sampling method', 'field.habitat': 'Habitat', 'field.collector': 'Collector',
    'field.field_number': 'Field number', 'field.storage_location': 'Storage location',
    'field.loan_status': 'Loan', 'field.loaned_to': 'Loaned to', 'field.loan_date': 'Loan date',
    'field.internal_notes': 'Internal notes', 'field.title': 'Title', 'field.year': 'Year',
    'field.insect_group': 'Insect group', 'field.email': 'E-mail', 'field.password': 'Password',
    'field.measurement': (p) => `Measurement ${p.n}`, 'field.trait': 'trait', 'field.value': 'value', 'field.unit': 'unit',

    'file.collection_csv': 'entomobase_collection', 'file.project_csv': (p) => `project_${p.id}_specimens`,
    'file.full_suffix': '_full', 'file.collection_dwc': 'entomobase_darwincore',
    'file.project_dwc': (p) => `project_${p.id}_darwincore`, 'file.import_template': 'entomobase_import_template',
    'template.default_trait': 'Body length',
    'template.header': ['Catalog Number', 'Order', 'Family', 'Species', 'Collection Date', 'Locality', 'Latitude', 'Longitude', 'Elevation (m)', 'Sex', 'Life Stage', 'Image', 'Notes'],
    'template.example': ['EX-0001', 'Coleoptera', 'Coccinellidae', 'Coccinella septempunctata', '2025-03-14', 'Rio Doce State Park', '-19.75', '-42.60', '250', 'female', 'adult', 'EX-0001.jpg', '']
  }
};

// values with a fixed vocabulary are stored in Portuguese; this is how they read in each language
const VOCABULARY = {
  sex: { macho: 'male', 'fêmea': 'female', indeterminado: 'undetermined' },
  life_stage: { adulto: 'adult', 'operária': 'worker', soldado: 'soldier', rainha: 'queen', ninfa: 'nymph', larva: 'larva', pupa: 'pupa' },
  loan_status: { 'no acervo': 'in collection', emprestado: 'on loan', 'em análise': 'under study' },
  sampling_method: {
    'armadilha de queda': 'pitfall trap', 'armadilha luminosa': 'light trap', 'armadilha Malaise': 'Malaise trap',
    'rede entomológica': 'insect net', 'busca ativa': 'active search', 'guarda-chuva entomológico': 'beating sheet'
  }
};

// how a stored value reads in lang; free text (not in the vocabulary) is shown as typed
function displayValue(lang, field, value) {
  if (lang === 'pt' || !value || !VOCABULARY[field]) return value;
  return VOCABULARY[field][value] ?? value;
}

// the stored form of a value typed or imported in either language (ignores case)
function storedValue(field, value) {
  if (!value || !VOCABULARY[field]) return value;
  const typed = value.trim().toLowerCase();
  for (const [stored, english] of Object.entries(VOCABULARY[field])) {
    if (stored.toLowerCase() === typed || english.toLowerCase() === typed) return stored;
  }
  return value;
}

// keys missing in a language are collected here, so the tests can tell when a text was not translated
const missingKeys = new Set();

// returns the message for key in lang, filling in params; falls back to Portuguese, then to the key itself
function translate(lang, key, params = {}) {
  let message = (MESSAGES[lang] || {})[key];
  if (message === undefined) {
    if (lang !== 'pt') missingKeys.add(key);
    message = MESSAGES.pt[key];
  }
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
