from sqlalchemy import inspect, text

import models
from database import SessionLocal, engine
from seguranca import gerar_hash, ja_e_hash


# adiciona colunas novas em bancos já existentes (SQLite ou PostgreSQL)
def migrar_colunas():
    novas = {
        "especimes": [
            ("familia", "VARCHAR"), ("altitude_m", "FLOAT"), ("sexo", "VARCHAR"),
            ("estagio", "VARCHAR"), ("imagem_arquivo", "VARCHAR"),
            ("determinador", "VARCHAR"), ("data_determinacao", "DATE"), ("metodo_coleta", "VARCHAR"),
            ("habitat", "VARCHAR"), ("coletor", "VARCHAR"), ("numero_campo", "VARCHAR"),
            ("localizacao_fisica", "VARCHAR"), ("emprestimo_situacao", "VARCHAR"),
            ("emprestimo_para", "VARCHAR"), ("emprestimo_data", "DATE"), ("notas_internas", "VARCHAR"),
        ],
        "projetos": [("descricao", "VARCHAR")],
    }
    inspetor = inspect(engine)
    with engine.begin() as conn:
        for tabela, colunas in novas.items():
            existentes = {c["name"] for c in inspetor.get_columns(tabela)}
            for nome, tipo in colunas:
                if nome not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))


# copia as medições antigas (pronoto e chifre) para a tabela de medidas por traço
# só roda na primeira vez em que a tabela nova aparece
def migrar_medicoes(tabelas_antes: set):
    if "medidas" in tabelas_antes or "medicoes" not in tabelas_antes:
        return
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO medidas (especime_id, traco, valor, unidade) "
            "SELECT especime_id, 'Largura do pronoto', largura_pronoto_mm, 'mm' FROM medicoes "
            "WHERE largura_pronoto_mm IS NOT NULL"
        ))
        conn.execute(text(
            "INSERT INTO medidas (especime_id, traco, valor, unidade) "
            "SELECT especime_id, 'Tamanho do chifre', tamanho_chifre_mm, 'mm' FROM medicoes "
            "WHERE tamanho_chifre_mm IS NOT NULL"
        ))


# senhas guardadas em texto puro por versões antigas passam a ser guardadas só como hash
def migrar_senhas():
    db = SessionLocal()
    try:
        for usuario in db.query(models.Usuario).all():
            if not ja_e_hash(usuario.senha):
                usuario.senha = gerar_hash(usuario.senha)
        db.commit()
    finally:
        db.close()


# cria as tabelas que faltam e aplica as migrações; seguro para rodar várias vezes
# é chamada ao iniciar a API e pelos scripts (seed.py, criar_admin.py), nunca ao importar um módulo
def inicializar_banco():
    tabelas_antes = set(inspect(engine).get_table_names())
    models.Base.metadata.create_all(bind=engine)
    migrar_colunas()
    migrar_medicoes(tabelas_antes)
    migrar_senhas()
