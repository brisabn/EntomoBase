from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine

models.Base.metadata.create_all(bind=engine)
app = FastAPI(title="EntomoBase API", version="0.1.0")

# Configuração de CORS para permitir que o Frontend (Vue.js) se comunique com a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restringir para a URL do frontend
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