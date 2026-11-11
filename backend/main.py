import csv
import io
import os
import re
import secrets
import urllib.parse
import zipfile
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.responses import StreamingResponse, Response
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import func, inspect, text, or_
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

import gbif
import models
import schemas
from database import SessionLocal, engine, get_db
from demo_imagens import gerar_svg
from seguranca import gerar_hash, ja_e_hash, precisa_novo_hash, verificar_senha

# a migração das medidas só roda na primeira vez em que a tabela nova aparece
_tabelas_antes = set(inspect(engine).get_table_names())
models.Base.metadata.create_all(bind=engine)


# adiciona colunas novas em bancos já existentes (SQLite ou PostgreSQL)
def migrar_colunas():
    novas = {
        "especimes": [
            ("familia", "VARCHAR"), ("altitude_m", "FLOAT"), ("sexo", "VARCHAR"),
            ("estagio", "VARCHAR"), ("imagem_arquivo", "VARCHAR"),
            ("determinador", "VARCHAR"), ("data_determinacao", "DATE"), ("metodo_coleta", "VARCHAR"),
            ("habitat", "VARCHAR"), ("coletor", "VARCHAR"), ("numero_campo", "VARCHAR"),
            ("localizacao_fisica", "VARCHAR"), ("emprestimo_situacao", "VARCHAR"),
            ("emprestimo_para", "VARCHAR"), ("emprestimo_data", "DATE"), ("notas_internas", "VARCHAR"),
        ],
        "projetos": [("descricao", "VARCHAR")],
    }
    inspetor = inspect(engine)
    with engine.begin() as conn:
        for tabela, colunas in novas.items():
            existentes = {c["name"] for c in inspetor.get_columns(tabela)}
            for nome, tipo in colunas:
                if nome not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))


# copia as medições antigas (pronoto e chifre) para a tabela de medidas por traço
def migrar_medicoes():
    if "medidas" in _tabelas_antes or "medicoes" not in _tabelas_antes:
        return
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO medidas (especime_id, traco, valor, unidade) "
            "SELECT especime_id, 'Largura do pronoto', largura_pronoto_mm, 'mm' FROM medicoes "
            "WHERE largura_pronoto_mm IS NOT NULL"
        ))
        conn.execute(text(
            "INSERT INTO medidas (especime_id, traco, valor, unidade) "
            "SELECT especime_id, 'Tamanho do chifre', tamanho_chifre_mm, 'mm' FROM medicoes "
            "WHERE tamanho_chifre_mm IS NOT NULL"
        ))


# senhas guardadas em texto puro por versões antigas passam a ser guardadas só como hash
def migrar_senhas():
    db = SessionLocal()
    try:
        for usuario in db.query(models.Usuario).all():
            if not ja_e_hash(usuario.senha):
                usuario.senha = gerar_hash(usuario.senha)
        db.commit()
    finally:
        db.close()


migrar_colunas()
migrar_medicoes()
migrar_senhas()

app = FastAPI(title="EntomoBase API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuração de Segurança JWT ---
ALGORITHM = "HS256"


# a chave vem do ambiente; sem ela a API só sobe em modo de desenvolvimento (ENTOMOBASE_ENV=dev),
# com uma chave aleatória que muda a cada início e invalida os logins anteriores
def carregar_chave_secreta() -> str:
    chave = os.getenv("SECRET_KEY")
    if chave:
        return chave
    if os.getenv("ENTOMOBASE_ENV") == "dev":
        print("AVISO: SECRET_KEY não definida; usando uma chave temporária (modo dev).")
        return secrets.token_urlsafe(32)
    raise RuntimeError(
        "SECRET_KEY não definida. Defina a variável de ambiente SECRET_KEY, "
        "ou use ENTOMOBASE_ENV=dev apenas em desenvolvimento."
    )


SECRET_KEY = carregar_chave_secreta()


def verificar_acesso(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente ou inválido")
    token = authorization.split(" ")[1]
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente.")


# não exige login; só informa se o token enviado é válido
def usuario_logado(authorization: str = Header(None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    try:
        jwt.decode(authorization.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False


# --- Autenticação ---
# não existe usuário padrão: o primeiro é criado com `python criar_admin.py email@exemplo.br`
@app.post("/login")
def login(credenciais: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(
        func.lower(models.Usuario.email) == credenciais.email.strip().lower()
    ).first()
    if not verificar_senha(credenciais.senha, usuario.senha if usuario else None):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    if precisa_novo_hash(usuario.senha):
        usuario.senha = gerar_hash(credenciais.senha)
        db.commit()

    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": usuario.email, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "email": usuario.email}


# --- Rotas de Projetos ---
@app.post("/projetos", response_model=schemas.ProjetoResponse, status_code=201)
def criar_projeto(projeto: schemas.ProjetoCreate, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    db_projeto = models.Projeto(**projeto.model_dump())
    db.add(db_projeto)
    db.commit()
    db.refresh(db_projeto)
    return db_projeto


@app.get("/projetos", response_model=List[schemas.ProjetoResponse])
def listar_projetos(
    ano: Optional[int] = None, grupo_insetos: Optional[str] = None,
    local_coleta: Optional[str] = None, finalizado: Optional[bool] = None,
    logado: bool = Depends(usuario_logado), db: Session = Depends(get_db)
):
    query = db.query(models.Projeto)
    # visitantes só veem projetos concluídos; o token é verificado de verdade
    if not logado:
        query = query.filter(models.Projeto.finalizado == True)
    elif finalizado is not None:
        query = query.filter(models.Projeto.finalizado == finalizado)
    if ano: query = query.filter(models.Projeto.ano == ano)
    if grupo_insetos: query = query.filter(models.Projeto.grupo_insetos.ilike(f"%{grupo_insetos}%"))
    if local_coleta: query = query.filter(models.Projeto.local_coleta.ilike(f"%{local_coleta}%"))
    return query.order_by(models.Projeto.ano.desc(), models.Projeto.id).all()


@app.put("/projetos/{projeto_id}", response_model=schemas.ProjetoResponse)
def atualizar_projeto(projeto_id: int, dados: schemas.ProjetoUpdate, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    db_projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if not db_projeto: raise HTTPException(status_code=404, detail="Projeto não encontrado")
    for key, value in dados.model_dump(exclude_unset=True).items():
        setattr(db_projeto, key, value)
    db.commit()
    db.refresh(db_projeto)
    return db_projeto


@app.delete("/projetos/{projeto_id}", status_code=204)
def deletar_projeto(projeto_id: int, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    db_projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if not db_projeto: raise HTTPException(status_code=404, detail="Projeto não encontrado")
    db.delete(db_projeto)
    db.commit()
    return None


# --- Rotas de Espécimes ---
def filtrar_visiveis(query, logado: bool):
    # visitantes não veem espécimes de projetos ainda em andamento
    if logado:
        return query
    return query.outerjoin(models.Projeto, models.Especime.projeto_id == models.Projeto.id).filter(
        or_(models.Especime.projeto_id.is_(None), models.Projeto.finalizado == True)
    )


# visitantes recebem o espécime sem os campos internos; a remoção é feita aqui, no servidor
def saida_especime(especime: models.Especime, logado: bool) -> dict:
    exclusao = None if logado else schemas.CAMPOS_INTERNOS
    return schemas.EspecimeResponse.model_validate(especime).model_dump(mode="json", exclude=exclusao)


def trocar_medidas(especime: models.Especime, medidas):
    especime.medidas.clear()
    for m in medidas:
        especime.medidas.append(models.Medida(**m.model_dump()))


@app.post("/especimes", response_model=schemas.EspecimeResponse, status_code=201)
def criar_especime(especime: schemas.EspecimeCreate, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    if db.query(models.Especime).filter(models.Especime.codigo_etiqueta == especime.codigo_etiqueta).first():
        raise HTTPException(status_code=400, detail="Código de etiqueta já cadastrado.")
    db_especime = models.Especime(**especime.model_dump(exclude={"medidas"}))
    trocar_medidas(db_especime, especime.medidas or [])
    db.add(db_especime)
    db.commit()
    db.refresh(db_especime)
    return db_especime


@app.get("/especimes")
def listar_especimes(
    especie: Optional[str] = None, projeto_id: Optional[int] = None,
    logado: bool = Depends(usuario_logado), db: Session = Depends(get_db)
):
    query = filtrar_visiveis(db.query(models.Especime), logado).options(selectinload(models.Especime.medidas))
    if especie: query = query.filter(models.Especime.especie.ilike(f"%{especie}%"))
    if projeto_id: query = query.filter(models.Especime.projeto_id == projeto_id)
    especimes = query.order_by(models.Especime.grupo_insetos, models.Especime.especie, models.Especime.codigo_etiqueta).all()
    return [saida_especime(e, logado) for e in especimes]


@app.put("/especimes/{especime_id}", response_model=schemas.EspecimeResponse)
def atualizar_especime(especime_id: int, dados: schemas.EspecimeUpdate, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    especime = db.query(models.Especime).filter(models.Especime.id == especime_id).first()
    if not especime: raise HTTPException(status_code=404, detail="Espécime não encontrado.")

    obrigatorios = {"codigo_etiqueta", "grupo_insetos", "especie"}
    campos = {
        k: v for k, v in dados.model_dump(exclude_unset=True, exclude={"medidas"}).items()
        if not (v is None and k in obrigatorios)
    }
    novo_codigo = campos.get("codigo_etiqueta")
    if novo_codigo and novo_codigo != especime.codigo_etiqueta:
        if db.query(models.Especime).filter(models.Especime.codigo_etiqueta == novo_codigo).first():
            raise HTTPException(status_code=400, detail="Código de etiqueta já cadastrado.")
    for key, value in campos.items():
        setattr(especime, key, value)

    # medidas enviadas substituem as anteriores; se não vierem, ficam como estão
    if dados.medidas is not None:
        trocar_medidas(especime, dados.medidas)
    db.commit()
    db.refresh(especime)
    return especime


@app.delete("/especimes/{especime_id}", status_code=204)
def deletar_especime(especime_id: int, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    especime = db.query(models.Especime).filter(models.Especime.id == especime_id).first()
    if not especime: raise HTTPException(status_code=404, detail="Espécime não encontrado.")
    db.delete(especime)
    db.commit()
    return None


# --- Importação em lote ---
def mensagem_validacao(erro: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in erro.errors())


@app.post("/especimes/importar", response_model=schemas.ImportarRelatorio)
def importar_especimes(
    pedido: schemas.ImportarPedido, simular: bool = False, validar_nomes: bool = True,
    db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)
):
    if pedido.projeto_id is not None:
        if not db.query(models.Projeto).filter(models.Projeto.id == pedido.projeto_id).first():
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

    ids_projetos = {p.id for p in db.query(models.Projeto.id).all()}
    erros = []
    validos = []
    vistos = {}
    for posicao, bruto in enumerate(pedido.linhas, start=1):
        numero = bruto.get("linha") or posicao
        try:
            item = schemas.EspecimeCreate(**bruto)
        except ValidationError as e:
            erros.append(schemas.ImportarErro(linha=numero, codigo_etiqueta=str(bruto.get("codigo_etiqueta") or ""), mensagem=mensagem_validacao(e)))
            continue
        item.codigo_etiqueta = item.codigo_etiqueta.strip()
        if pedido.projeto_id is not None:
            item.projeto_id = pedido.projeto_id
        elif item.projeto_id is not None and item.projeto_id not in ids_projetos:
            erros.append(schemas.ImportarErro(linha=numero, codigo_etiqueta=item.codigo_etiqueta, mensagem=f"projeto_id {item.projeto_id} não existe"))
            continue
        if item.codigo_etiqueta in vistos:
            erros.append(schemas.ImportarErro(linha=numero, codigo_etiqueta=item.codigo_etiqueta, mensagem=f"código repetido no arquivo (primeira vez na linha {vistos[item.codigo_etiqueta]})"))
            continue
        vistos[item.codigo_etiqueta] = numero
        validos.append((numero, item))

    existentes = {}
    codigos = list(vistos.keys())
    for i in range(0, len(codigos), 500):
        for e in db.query(models.Especime).filter(models.Especime.codigo_etiqueta.in_(codigos[i:i + 500])).all():
            existentes[e.codigo_etiqueta] = e

    criados = atualizados = ignorados = 0
    for numero, item in validos:
        atual = existentes.get(item.codigo_etiqueta)
        if atual is None:
            criados += 1
            if not simular and not erros:
                novo = models.Especime(**item.model_dump(exclude={"medidas"}))
                trocar_medidas(novo, item.medidas or [])
                db.add(novo)
        elif pedido.duplicados == "atualizar":
            atualizados += 1
            if not simular and not erros:
                for k, v in item.model_dump(exclude_unset=True, exclude={"medidas", "codigo_etiqueta"}).items():
                    if v is not None:
                        setattr(atual, k, v)
                if item.medidas:
                    trocar_medidas(atual, item.medidas)
        else:
            ignorados += 1

    if not simular:
        if erros:
            db.rollback()
            raise HTTPException(status_code=422, detail=f"{len(erros)} linha(s) com erro; nada foi importado.")
        db.commit()

    avisos = avisos_taxonomicos(validos, db) if simular and validar_nomes else []
    return schemas.ImportarRelatorio(
        simulacao=simular, total=len(pedido.linhas), criados=criados,
        atualizados=atualizados, ignorados=ignorados, erros=erros[:200], avisos=avisos,
    )


ROTULOS_OK = {"ok"}


# consulta o GBIF para os nomes distintos do arquivo; os avisos nunca impedem a importação
def avisos_taxonomicos(validos, db: Session) -> List[schemas.ImportarAviso]:
    contagem = {}
    for _, item in validos:
        nome = item.especie.strip()
        contagem[nome] = contagem.get(nome, 0) + 1
    if not contagem:
        return []
    nomes = list(contagem)[:150]
    resultados = gbif.validar_nomes(nomes, db)
    avisos = []
    indisponiveis = 0
    for nome in nomes:
        r = resultados.get(nome, {})
        situacao = r.get("situacao", "indisponivel")
        if situacao in ROTULOS_OK:
            continue
        if situacao == "indisponivel":
            indisponiveis += contagem[nome]
            continue
        avisos.append(schemas.ImportarAviso(nome=nome, tipo=situacao, sugestao=r.get("sugestao"), linhas=contagem[nome]))
    if indisponiveis:
        avisos.append(schemas.ImportarAviso(nome="", tipo="indisponivel", linhas=indisponiveis))
    return avisos


@app.post("/taxonomia/validar", response_model=List[schemas.NomeValidado])
def validar_nomes_cientificos(
    pedido: schemas.ValidarNomesPedido, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)
):
    resultados = gbif.validar_nomes(pedido.nomes, db)
    return [schemas.NomeValidado(nome=n, **r) for n, r in resultados.items()]


# --- Exportação ---
COLUNAS_BASE = [
    "Codigo Etiqueta", "Ordem", "Familia", "Especie", "Data Coleta", "Local Coleta", "Latitude", "Longitude",
    "Altitude (m)", "Sexo", "Estagio", "Determinador", "Data Determinacao", "Metodo Coleta", "Habitat",
    "Imagem", "Projeto", "Notas",
]
# só aparecem no CSV completo, que exige login
COLUNAS_INTERNAS = [
    "Coletor", "Numero Campo", "Localizacao Fisica", "Emprestimo", "Emprestado Para", "Data Emprestimo", "Notas Internas",
]


@app.get("/exportar/csv")
def exportar_especimes_csv(
    projeto_id: Optional[int] = None, completo: bool = False,
    logado: bool = Depends(usuario_logado), db: Session = Depends(get_db)
):
    if completo and not logado:
        raise HTTPException(status_code=401, detail="O CSV completo exige login.")
    query = filtrar_visiveis(db.query(models.Especime), logado).options(
        selectinload(models.Especime.medidas), selectinload(models.Especime.projeto)
    )
    if projeto_id: query = query.filter(models.Especime.projeto_id == projeto_id)
    especimes = query.order_by(models.Especime.id).all()

    # uma coluna por traço medido, no formato "Traço (unidade)", que o importador também entende
    tracos = []
    for esp in especimes:
        for m in esp.medidas:
            chave = (m.traco, m.unidade or "mm")
            if chave not in tracos:
                tracos.append(chave)

    output = io.StringIO()
    # BOM para o Excel abrir os acentos corretamente
    output.write("\ufeff")
    writer = csv.writer(output)
    cabecalho = COLUNAS_BASE + (COLUNAS_INTERNAS if completo else [])
    writer.writerow(cabecalho + [f"{t} ({u})" for t, u in tracos])
    for esp in especimes:
        valores = {(m.traco, m.unidade or "mm"): m.valor for m in esp.medidas}
        linha = [
            esp.codigo_etiqueta, esp.grupo_insetos, esp.familia, esp.especie, esp.data_coleta, esp.local_coleta,
            esp.latitude, esp.longitude, esp.altitude_m, esp.sexo, esp.estagio, esp.determinador,
            esp.data_determinacao, esp.metodo_coleta, esp.habitat, esp.imagem_arquivo,
            esp.projeto.titulo if esp.projeto else None, esp.notas,
        ]
        if completo:
            linha += [
                esp.coletor, esp.numero_campo, esp.localizacao_fisica, esp.emprestimo_situacao,
                esp.emprestimo_para, esp.emprestimo_data, esp.notas_internas,
            ]
        writer.writerow(linha + [valores.get(chave) for chave in tracos])
    output.seek(0)
    nome = "acervo_entomobase_completo.csv" if completo else "acervo_entomobase.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome}"},
    )


# --- Darwin Core ---
# ajuste estes valores para os da coleção antes de publicar no GBIF
DWC_INSTITUICAO = "UFMG"
DWC_COLECAO = "EntomoBase"
DWC_LICENCA = "http://creativecommons.org/licenses/by/4.0/legalcode"
DWC_ENDERECO_ZENODO = "https://zenodo.org/records/{registro}/files/{arquivo}"

DWC_CAMPOS = [
    "occurrenceID", "basisOfRecord", "institutionCode", "collectionCode", "catalogNumber", "datasetName",
    "license", "kingdom", "class", "order", "family", "scientificName", "eventDate", "locality",
    "decimalLatitude", "decimalLongitude", "geodeticDatum", "minimumElevationInMeters", "sex", "lifeStage",
    "identifiedBy", "dateIdentified", "samplingProtocol", "habitat", "associatedMedia", "occurrenceRemarks",
]
DWC_TERMOS = "http://rs.tdwg.org/dwc/terms/"


def midia_zenodo(esp: models.Especime) -> Optional[str]:
    url = esp.projeto.dataset_externo_url if esp.projeto else None
    if esp.fotografia_url and esp.fotografia_url.startswith("http"):
        return esp.fotografia_url
    if not (url and esp.imagem_arquivo):
        return None
    achado = re.search(r"zenodo\.org/records?/(\d+)", url, re.I) or re.search(r"10\.5281/zenodo\.(\d+)", url, re.I)
    # ids que começam com 0 são os dos dados fictícios
    if not achado or achado.group(1).startswith("0"):
        return None
    return DWC_ENDERECO_ZENODO.format(registro=achado.group(1), arquivo=urllib.parse.quote(esp.imagem_arquivo))


def meta_xml() -> str:
    def campos(lista, inicio):
        return "\n".join(
            f'    <field index="{i}" term="{DWC_TERMOS}{nome}"/>' for i, nome in enumerate(lista, start=inicio)
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<archive xmlns="http://rs.tdwg.org/dwc/text/">\n'
        '  <core encoding="UTF-8" fieldsTerminatedBy="," linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">\n'
        '    <files><location>occurrence.csv</location></files>\n'
        '    <id index="0"/>\n'
        f'{campos(DWC_CAMPOS[1:], 1)}\n'
        '  </core>\n'
        '  <extension encoding="UTF-8" fieldsTerminatedBy="," linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/MeasurementOrFact">\n'
        '    <files><location>measurementorfact.csv</location></files>\n'
        '    <coreid index="0"/>\n'
        f'{campos(["measurementType", "measurementValue", "measurementUnit"], 1)}\n'
        '  </extension>\n'
        '</archive>\n'
    )


# a exportação Darwin Core é sempre pública: só projetos concluídos e nenhum campo interno
@app.get("/exportar/dwc")
def exportar_darwin_core(projeto_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = filtrar_visiveis(db.query(models.Especime), False).options(
        selectinload(models.Especime.medidas), selectinload(models.Especime.projeto)
    )
    if projeto_id: query = query.filter(models.Especime.projeto_id == projeto_id)
    especimes = query.order_by(models.Especime.id).all()

    ocorrencias = io.StringIO()
    medidas = io.StringIO()
    w_oc = csv.writer(ocorrencias, lineterminator="\n")
    w_me = csv.writer(medidas, lineterminator="\n")
    w_oc.writerow(DWC_CAMPOS)
    w_me.writerow(["occurrenceID", "measurementType", "measurementValue", "measurementUnit"])
    for esp in especimes:
        ocorrencia = f"{DWC_INSTITUICAO}:{DWC_COLECAO}:{esp.codigo_etiqueta}"
        tem_coordenadas = esp.latitude is not None and esp.longitude is not None
        w_oc.writerow([
            ocorrencia, "PreservedSpecimen", DWC_INSTITUICAO, DWC_COLECAO, esp.codigo_etiqueta,
            esp.projeto.titulo if esp.projeto else "", DWC_LICENCA, "Animalia", "Insecta", esp.grupo_insetos,
            esp.familia, esp.especie, esp.data_coleta, esp.local_coleta,
            esp.latitude, esp.longitude, "WGS84" if tem_coordenadas else "", esp.altitude_m, esp.sexo, esp.estagio,
            esp.determinador, esp.data_determinacao, esp.metodo_coleta, esp.habitat, midia_zenodo(esp), esp.notas,
        ])
        for med in esp.medidas:
            w_me.writerow([ocorrencia, med.traco, med.valor, med.unidade])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr("occurrence.csv", ocorrencias.getvalue())
        pacote.writestr("measurementorfact.csv", medidas.getvalue())
        pacote.writestr("meta.xml", meta_xml())
    return Response(
        buffer.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=entomobase_darwincore.zip"},
    )


# --- Imagens de demonstração (só para os dados fictícios; pode apagar esta rota) ---
@app.get("/demo/imagem/{arquivo}")
def imagem_demo(arquivo: str, db: Session = Depends(get_db)):
    esp = db.query(models.Especime).filter(models.Especime.imagem_arquivo == arquivo).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    svg = gerar_svg(esp.grupo_insetos, esp.familia or "", esp.especie, esp.id, esp.codigo_etiqueta, esp.sexo or "")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})