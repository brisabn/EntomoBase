from fastapi import FastAPI, Depends, HTTPException
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

@app.get("/")
def read_root():
    return {"status": "EntomoBase API está ativa e operando!"}

@app.get("/ping")
def ping():
    return {"message": "pong"}

# --- Rotas de Projetos ---
@app.post("/projetos", response_model=schemas.ProjetoResponse, status_code=201)
def criar_projeto(projeto: schemas.ProjetoCreate, db: Session = Depends(get_db)):
    db_projeto = models.Projeto(**projeto.model_dump())
    db.add(db_projeto)
    db.commit()
    db.refresh(db_projeto)
    return db_projeto

@app.get("/projetos", response_model=List[schemas.ProjetoResponse])
def listar_projetos(db: Session = Depends(get_db)):
    return db.query(models.Projeto).all()

# --- Rotas de Espécimes ---
@app.post("/especimes", response_model=schemas.EspecimeResponse, status_code=201)
def criar_especime(especime: schemas.EspecimeCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Especime).filter(
        models.Especime.codigo_etiqueta == especime.codigo_etiqueta
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Código de etiqueta já cadastrado.")

    dados_especime = especime.model_dump(exclude={"medicoes"})
    db_especime = models.Especime(**dados_especime)
    db.add(db_especime)
    db.commit()
    db.refresh(db_especime)

    for med in especime.medicoes or []:
        db_medicao = models.Medicao(**med.model_dump(), especime_id=db_especime.id)
        db.add(db_medicao)
    
    db.commit()
    db.refresh(db_especime)
    return db_especime

@app.get("/especimes", response_model=List[schemas.EspecimeResponse])
def listar_especimes(
    especie: Optional[str] = None,
    projeto_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Especime)
    if especie:
        query = query.filter(models.Especime.especie.ilike(f"%{especie}%"))
    if projeto_id:
        query = query.filter(models.Especime.projeto_id == projeto_id)
    return query.all()

@app.delete("/especimes/{especime_id}", status_code=204)
def deletar_especime(especime_id: int, db: Session = Depends(get_db)):
    especime = db.query(models.Especime).filter(models.Especime.id == especime_id).first()
    if not especime:
        raise HTTPException(status_code=404, detail="Espécime não encontrado.")
    db.delete(especime)
    db.commit()
    return None