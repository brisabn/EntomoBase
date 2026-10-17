from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

# --- Schemas de Medição ---
class MedicaoBase(BaseModel):
    tamanho_chifre_mm: Optional[float] = Field(None, ge=0, description="Deve ser >= 0")
    largura_pronoto_mm: float = Field(..., gt=0, description="Deve ser > 0")

class MedicaoCreate(MedicaoBase):
    pass

class MedicaoResponse(MedicaoBase):
    id: int
    especime_id: int

    class Config:
        from_attributes = True


# --- Schemas de Espécime ---
class EspecimeBase(BaseModel):
    codigo_etiqueta: str = Field(..., min_length=1)
    especie: str = Field(..., min_length=1)
    data_coleta: Optional[date] = None
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


# --- Schemas de Projeto ---
class ProjetoBase(BaseModel):
    titulo: str = Field(..., min_length=1)
    status: Optional[str] = "Em andamento"
    publicacao_vinculada: Optional[str] = None

class ProjetoCreate(ProjetoBase):
    pass

class ProjetoResponse(ProjetoBase):
    id: int
    especimes: List[EspecimeResponse] = []

    class Config:
        from_attributes = True