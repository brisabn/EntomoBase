from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class MedicaoBase(BaseModel):
    tamanho_chifre_mm: Optional[float] = Field(None, ge=0)
    largura_pronoto_mm: float = Field(..., gt=0)

class MedicaoCreate(MedicaoBase):
    pass

class MedicaoResponse(MedicaoBase):
    id: int
    especime_id: int

    class Config:
        from_attributes = True


class EspecimeBase(BaseModel):
    codigo_etiqueta: str = Field(..., min_length=1)
    grupo_insetos: str = Field(..., min_length=1)
    especie: str = Field(..., min_length=1)
    data_coleta: Optional[date] = None
    local_coleta: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    fotografia_url: Optional[str] = None
    notas: Optional[str] = None
    projeto_id: Optional[int] = None

class EspecimeCreate(EspecimeBase):
    medicoes: Optional[List[MedicaoCreate]] = []

class EspecimeResponse(EspecimeBase):
    id: int
    medicoes: List[MedicaoResponse] = []

    class Config:
        from_attributes = True


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

class ProjetoCreate(ProjetoBase):
    pass

class ProjetoResponse(ProjetoBase):
    id: int
    especimes: List[EspecimeResponse] = []

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