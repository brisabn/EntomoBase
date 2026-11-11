from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime
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
    descricao = Column(String, nullable=True)

    especimes = relationship("Especime", back_populates="projeto", cascade="all, delete-orphan")


class Especime(Base):
    __tablename__ = "especimes"

    id = Column(Integer, primary_key=True, index=True)
    codigo_etiqueta = Column(String, unique=True, index=True, nullable=False)
    grupo_insetos = Column(String, index=True, nullable=False)
    familia = Column(String, index=True, nullable=True)
    especie = Column(String, index=True, nullable=False)
    data_coleta = Column(Date, nullable=True)
    local_coleta = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude_m = Column(Float, nullable=True)
    sexo = Column(String, nullable=True)
    estagio = Column(String, nullable=True)
    # nome do arquivo dentro do registro do Zenodo do projeto (ex.: COL-001.jpg)
    imagem_arquivo = Column(String, nullable=True)
    fotografia_url = Column(String, nullable=True)
    notas = Column(String, nullable=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"), nullable=True)

    # campos públicos de identificação e coleta
    determinador = Column(String, nullable=True)
    data_determinacao = Column(Date, nullable=True)
    metodo_coleta = Column(String, nullable=True)
    habitat = Column(String, nullable=True)

    # campos internos: só o laboratório logado vê (ver CAMPOS_INTERNOS em schemas.py)
    coletor = Column(String, nullable=True)
    numero_campo = Column(String, nullable=True)
    localizacao_fisica = Column(String, nullable=True)
    emprestimo_situacao = Column(String, nullable=True)
    emprestimo_para = Column(String, nullable=True)
    emprestimo_data = Column(Date, nullable=True)
    notas_internas = Column(String, nullable=True)

    projeto = relationship("Projeto", back_populates="especimes")
    medidas = relationship("Medida", back_populates="especime", cascade="all, delete-orphan", order_by="Medida.id")
    # tabela antiga, mantida só para não perder dados na migração
    medicoes = relationship("Medicao", back_populates="especime", cascade="all, delete-orphan")


class Medida(Base):
    __tablename__ = "medidas"

    id = Column(Integer, primary_key=True, index=True)
    especime_id = Column(Integer, ForeignKey("especimes.id"), nullable=False, index=True)
    traco = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    unidade = Column(String, nullable=False, default="mm")

    especime = relationship("Especime", back_populates="medidas")


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


# cache das consultas de nomes científicos ao GBIF
class Taxon(Base):
    __tablename__ = "taxons"

    id = Column(Integer, primary_key=True, index=True)
    nome_informado = Column(String, unique=True, index=True, nullable=False)
    situacao = Column(String, nullable=False)
    sugestao = Column(String, nullable=True)
    chave_gbif = Column(Integer, nullable=True)
    familia = Column(String, nullable=True)
    ordem = Column(String, nullable=True)
    consultado_em = Column(DateTime, nullable=False)