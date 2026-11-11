import sqlite3

import models
from sqlalchemy import create_engine

# the database as the first versions created it: Portuguese names, plain text passwords, fixed measurements
OLD_SCHEMA = """
create table usuarios (id integer not null, email varchar not null, senha varchar not null, primary key (id));
create table projetos (id integer not null, titulo varchar not null, ano integer not null, grupo_insetos varchar not null,
    tracos_medidos varchar, local_coleta varchar, capa_url varchar, dataset_externo_url varchar, finalizado boolean,
    publicacao_vinculada varchar, primary key (id));
create table especimes (id integer not null, codigo_etiqueta varchar not null, grupo_insetos varchar not null,
    especie varchar not null, data_coleta date, local_coleta varchar, latitude float, longitude float, notas varchar,
    fotografia_url varchar, projeto_id integer, primary key (id), foreign key(projeto_id) references projetos (id));
create table medicoes (id integer not null, especime_id integer not null, tamanho_chifre_mm float, largura_pronoto_mm float not null,
    primary key (id), foreign key(especime_id) references especimes (id));
create table taxons (id integer not null, nome_informado varchar not null, situacao varchar not null, sugestao varchar,
    chave_gbif integer, familia varchar, ordem varchar, consultado_em datetime not null, primary key (id));
create unique index ix_especimes_codigo_etiqueta on especimes (codigo_etiqueta);
create index ix_especimes_id on especimes (id);
create index ix_projetos_titulo on projetos (titulo);
insert into usuarios (email, senha) values ('a@lab.br', 'plain-password');
insert into projetos (id, titulo, ano, grupo_insetos, finalizado) values (1, 'Old project', 2024, 'Coleoptera', 1);
insert into especimes (id, codigo_etiqueta, grupo_insetos, especie, projeto_id) values (1, 'X-1', 'Coleoptera', 'Dynastes hercules', 1);
insert into medicoes (especime_id, tamanho_chifre_mm, largura_pronoto_mm) values (1, 40.5, 20.0);
insert into taxons (nome_informado, situacao, consultado_em) values ('A b', 'sinonimo', '2025-01-01 00:00:00');
"""


def rows(db_path, sql):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def old_database(tmp_path, name="old.db"):
    path = str(tmp_path / name)
    con = sqlite3.connect(path)
    con.executescript(OLD_SCHEMA)
    con.commit()
    con.close()
    return path


# a database as the API created it right before Alembic: current English schema, no alembic_version table
def pre_alembic_database(tmp_path, name="pre_alembic.db"):
    path = str(tmp_path / name)
    engine = create_engine("sqlite:///" + path.replace("\\", "/"))
    models.Base.metadata.create_all(bind=engine)
    engine.dispose()
    con = sqlite3.connect(path)
    con.executescript("""
        insert into users (email, password_hash) values ('b@lab.br', 'plain-password');
        insert into projects (id, title, year, insect_group, finished) values (1, 'Current project', 2025, 'Lepidoptera', 1);
        insert into specimens (id, catalog_number, insect_order, species, project_id) values (1, 'Y-1', 'Lepidoptera', 'Morpho helenor', 1);
        insert into measurements (specimen_id, trait, value, unit) values (1, 'Envergadura alar', 120.5, 'mm');
    """)
    con.commit()
    con.close()
    return path
