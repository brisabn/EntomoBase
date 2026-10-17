from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from sqlalchemy.orm import relationship
from database import Base

class Projeto(Base):
    __tablename__ = "projetos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False, index=True)
    status = Column(String, default="Em andamento")
    publicacao_vinculada = Column(String, nullable=True)

    especimes = relationship("Especime", back_populates="projeto")


class Especime(Base):
    __tablename__ = "especimes"

    id = Column(Integer, primary_key=True, index=True)
    codigo_etiqueta = Column(String, unique=True, index=True, nullable=False)
    especie = Column(String, index=True, nullable=False)
    data_coleta = Column(Date, nullable=True)
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