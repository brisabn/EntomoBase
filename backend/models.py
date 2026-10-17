from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from database import Base

class Projeto(Base):
    __tablename__ = "projetos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False, index=True)
    ano = Column(Integer, nullable=False, index=True)
    grupo_insetos = Column(String, nullable=False, index=True)
    tracos_medidos = Column(String, nullable=True)
    local_coleta = Column(String, nullable=True)
    capa_url = Column(String, nullable=True)
    dataset_externo_url = Column(String, nullable=True)
    finalizado = Column(Boolean, default=False)
    publicacao_vinculada = Column(String, nullable=True)

    especimes = relationship("Especime", back_populates="projeto", cascade="all, delete-orphan")


class Especime(Base):
    __tablename__ = "especimes"

    id = Column(Integer, primary_key=True, index=True)
    codigo_etiqueta = Column(String, unique=True, index=True, nullable=False)
    grupo_insetos = Column(String, index=True, nullable=False)
    especie = Column(String, index=True, nullable=False)
    data_coleta = Column(Date, nullable=True)
    local_coleta = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    fotografia_url = Column(String, nullable=True)
    notas = Column(String, nullable=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"), nullable=True)

    projeto = relationship("Projeto", back_populates="especimes")
    medicoes = relationship("Medicao", back_populates="especime", cascade="all, delete-orphan")


class Medicao(Base):
    __tablename__ = "medicoes"

    id = Column(Integer, primary_key=True, index=True)
    especime_id = Column(Integer, ForeignKey("especimes.id"), nullable=False)
    tamanho_chifre_mm = Column(Float, nullable=True)
    largura_pronoto_mm = Column(Float, nullable=False)

    especime = relationship("Especime", back_populates="medicoes")

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    senha = Column(String, nullable=False)