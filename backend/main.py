import csv
import io
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.responses import StreamingResponse, Response
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import inspect, text, or_
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

import models
import schemas
from database import engine, get_db
from demo_imagens import gerar_svg

# a migração das medidas só roda na primeira vez em que a tabela nova aparece
_tabelas_antes = set(inspect(engine).get_table_names())
models.Base.metadata.create_all(bind=engine)


# adiciona colunas novas em bancos já existentes (SQLite ou PostgreSQL)
def migrar_colunas():
    novas = {
        "especimes": [
            ("familia", "VARCHAR"), ("altitude_m", "FLOAT"), ("sexo", "VARCHAR"),
            ("estagio", "VARCHAR"), ("imagem_arquivo", "VARCHAR"),
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


migrar_colunas()
migrar_medicoes()

app = FastAPI(title="EntomoBase API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuração de Segurança JWT ---
SECRET_KEY = "entomobase-secreto"
ALGORITHM = "HS256"


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


# Criar usuário padrão do laboratório se o banco estiver vazio
db_init = next(get_db())
if not db_init.query(models.Usuario).first():
    db_init.add(models.Usuario(email="admin@lab.br", senha="123"))
    db_init.commit()
db_init.close()


# --- Autenticação ---
@app.post("/login")
def login(credenciais: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == credenciais.email,
        models.Usuario.senha == credenciais.senha
    ).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

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


@app.get("/especimes", response_model=List[schemas.EspecimeResponse])
def listar_especimes(
    especie: Optional[str] = None, projeto_id: Optional[int] = None,
    logado: bool = Depends(usuario_logado), db: Session = Depends(get_db)
):
    query = filtrar_visiveis(db.query(models.Especime), logado).options(selectinload(models.Especime.medidas))
    if especie: query = query.filter(models.Especime.especie.ilike(f"%{especie}%"))
    if projeto_id: query = query.filter(models.Especime.projeto_id == projeto_id)
    return query.order_by(models.Especime.grupo_insetos, models.Especime.especie, models.Especime.codigo_etiqueta).all()


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
    pedido: schemas.ImportarPedido, simular: bool = False,
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

    return schemas.ImportarRelatorio(
        simulacao=simular, total=len(pedido.linhas), criados=criados,
        atualizados=atualizados, ignorados=ignorados, erros=erros[:200],
    )


# --- Exportação ---
COLUNAS_BASE = [
    "Codigo Etiqueta", "Ordem", "Familia", "Especie", "Data Coleta", "Local Coleta", "Latitude", "Longitude",
    "Altitude (m)", "Sexo", "Estagio", "Imagem", "Projeto", "Notas",
]


@app.get("/exportar/csv")
def exportar_especimes_csv(
    projeto_id: Optional[int] = None,
    logado: bool = Depends(usuario_logado), db: Session = Depends(get_db)
):
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
    output.write("﻿")
    writer = csv.writer(output)
    writer.writerow(COLUNAS_BASE + [f"{t} ({u})" for t, u in tracos])
    for esp in especimes:
        valores = {(m.traco, m.unidade or "mm"): m.valor for m in esp.medidas}
        writer.writerow([
            esp.codigo_etiqueta, esp.grupo_insetos, esp.familia, esp.especie, esp.data_coleta, esp.local_coleta,
            esp.latitude, esp.longitude, esp.altitude_m, esp.sexo, esp.estagio, esp.imagem_arquivo,
            esp.projeto.titulo if esp.projeto else None, esp.notas,
        ] + [valores.get(chave) for chave in tracos])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=acervo_entomobase.csv"},
    )


# --- Imagens de demonstração (só para os dados fictícios; pode apagar esta rota) ---
@app.get("/demo/imagem/{arquivo}")
def imagem_demo(arquivo: str, db: Session = Depends(get_db)):
    esp = db.query(models.Especime).filter(models.Especime.imagem_arquivo == arquivo).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    svg = gerar_svg(esp.grupo_insetos, esp.familia or "", esp.especie, esp.id, esp.codigo_etiqueta, esp.sexo or "")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})