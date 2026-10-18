from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class MedidaBase(BaseModel):
    traco: str = Field(..., min_length=1)
    valor: float = Field(..., ge=0)
    unidade: str = "mm"

class MedidaCreate(MedidaBase):
    pass

class MedidaResponse(MedidaBase):
    id: int

    class Config:
        from_attributes = True


class EspecimeBase(BaseModel):
    codigo_etiqueta: str = Field(..., min_length=1)
    grupo_insetos: str = Field(..., min_length=1)
    familia: Optional[str] = None
    especie: str = Field(..., min_length=1)
    data_coleta: Optional[date] = None
    local_coleta: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    altitude_m: Optional[float] = None
    sexo: Optional[str] = None
    estagio: Optional[str] = None
    imagem_arquivo: Optional[str] = None
    fotografia_url: Optional[str] = None
    notas: Optional[str] = None
    projeto_id: Optional[int] = None

class EspecimeCreate(EspecimeBase):
    medidas: Optional[List[MedidaCreate]] = []

class EspecimeUpdate(BaseModel):
    codigo_etiqueta: Optional[str] = Field(None, min_length=1)
    grupo_insetos: Optional[str] = Field(None, min_length=1)
    familia: Optional[str] = None
    especie: Optional[str] = Field(None, min_length=1)
    data_coleta: Optional[date] = None
    local_coleta: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    altitude_m: Optional[float] = None
    sexo: Optional[str] = None
    estagio: Optional[str] = None
    imagem_arquivo: Optional[str] = None
    fotografia_url: Optional[str] = None
    notas: Optional[str] = None
    projeto_id: Optional[int] = None
    medidas: Optional[List[MedidaCreate]] = None

class EspecimeResponse(EspecimeBase):
    id: int
    medidas: List[MedidaResponse] = []

    class Config:
        from_attributes = True


class ImportarPedido(BaseModel):
    projeto_id: Optional[int] = None
    duplicados: str = Field("ignorar", pattern="^(ignorar|atualizar)$")
    linhas: List[dict] = Field(..., max_length=5000)

class ImportarErro(BaseModel):
    linha: Optional[int] = None
    codigo_etiqueta: Optional[str] = None
    mensagem: str

class ImportarRelatorio(BaseModel):
    simulacao: bool
    total: int
    criados: int
    atualizados: int
    ignorados: int
    erros: List[ImportarErro]


class ProjetoBase(BaseModel):
    titulo: str = Field(..., min_length=1)
    ano: int = Field(..., ge=1900, le=2100)
    grupo_insetos: str = Field(..., min_length=1)
    tracos_medidos: Optional[str] = None
    local_coleta: Optional[str] = None
    capa_url: Optional[str] = None
    dataset_externo_url: Optional[str] = None
    finalizado: bool = False
    publicacao_vinculada: Optional[str] = None
    descricao: Optional[str] = None

class ProjetoCreate(ProjetoBase):
    pass

class ProjetoResponse(ProjetoBase):
    id: int

    class Config:
        from_attributes = True

class UsuarioLogin(BaseModel):
    email: str = Field(..., min_length=5)
    senha: str = Field(..., min_length=3)

class ProjetoUpdate(BaseModel):
    titulo: Optional[str] = None
    ano: Optional[int] = None
    grupo_insetos: Optional[str] = None
    tracos_medidos: Optional[str] = None
    local_coleta: Optional[str] = None
    capa_url: Optional[str] = None
    dataset_externo_url: Optional[str] = None
    finalizado: Optional[bool] = None
    publicacao_vinculada: Optional[str] = None
    descricao: Optional[str] = None