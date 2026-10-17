import csv
import io
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.responses import StreamingResponse
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="EntomoBase API", version="0.1.0")

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
    acesso_laboratorio: bool = False, db: Session = Depends(get_db)
):
    query = db.query(models.Projeto)
    if not acesso_laboratorio:
        query = query.filter(models.Projeto.finalizado == True)
    elif finalizado is not None:
        query = query.filter(models.Projeto.finalizado == finalizado)
    if ano: query = query.filter(models.Projeto.ano == ano)
    if grupo_insetos: query = query.filter(models.Projeto.grupo_insetos.ilike(f"%{grupo_insetos}%"))
    if local_coleta: query = query.filter(models.Projeto.local_coleta.ilike(f"%{local_coleta}%"))
    return query.all()

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
@app.post("/especimes", response_model=schemas.EspecimeResponse, status_code=201)
def criar_especime(especime: schemas.EspecimeCreate, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    if db.query(models.Especime).filter(models.Especime.codigo_etiqueta == especime.codigo_etiqueta).first():
        raise HTTPException(status_code=400, detail="Código de etiqueta já cadastrado.")
    dados_especime = especime.model_dump(exclude={"medicoes"})
    db_especime = models.Especime(**dados_especime)
    db.add(db_especime)
    db.commit()
    db.refresh(db_especime)
    for med in especime.medicoes or []:
        db.add(models.Medicao(**med.model_dump(), especime_id=db_especime.id))
    db.commit()
    db.refresh(db_especime)
    return db_especime

@app.get("/especimes", response_model=List[schemas.EspecimeResponse])
def listar_especimes(especie: Optional[str] = None, projeto_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Especime)
    if especie: query = query.filter(models.Especime.especie.ilike(f"%{especie}%"))
    if projeto_id: query = query.filter(models.Especime.projeto_id == projeto_id)
    return query.all()

@app.delete("/especimes/{especime_id}", status_code=204)
def deletar_especime(especime_id: int, db: Session = Depends(get_db), auth: None = Depends(verificar_acesso)):
    especime = db.query(models.Especime).filter(models.Especime.id == especime_id).first()
    if not especime: raise HTTPException(status_code=404, detail="Espécime não encontrado.")
    db.delete(especime)
    db.commit()
    return None

@app.get("/exportar/csv")
def exportar_especimes_csv(projeto_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Especime)
    if projeto_id: query = query.filter(models.Especime.projeto_id == projeto_id)
    especimes = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Codigo Etiqueta", "Grupo", "Especie", "Data Coleta", "Local Coleta", "Latitude", "Longitude", "Projeto ID", "Tamanho Chifre (mm)", "Largura Pronoto (mm)", "Notas"])
    for esp in especimes:
        if esp.medicoes:
            for med in esp.medicoes:
                writer.writerow([esp.id, esp.codigo_etiqueta, esp.grupo_insetos, esp.especie, esp.data_coleta, esp.local_coleta, esp.latitude, esp.longitude, esp.projeto_id, med.tamanho_chifre_mm, med.largura_pronoto_mm, esp.notas])
        else:
            writer.writerow([esp.id, esp.codigo_etiqueta, esp.grupo_insetos, esp.especie, esp.data_coleta, esp.local_coleta, esp.latitude, esp.longitude, esp.projeto_id, None, None, esp.notas])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=acervo_entomobase.csv"})