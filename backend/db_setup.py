from sqlalchemy import inspect, text

import models
from database import SessionLocal, engine
from security import hash_password, is_hash

# the schema used to have Portuguese names; each old table maps to its new name and renamed columns
LEGACY_SCHEMA = {
    "projetos": ("projects", {
        "titulo": "title", "ano": "year", "grupo_insetos": "insect_group", "tracos_medidos": "measured_traits",
        "local_coleta": "locality", "capa_url": "cover_url", "dataset_externo_url": "dataset_url",
        "finalizado": "finished", "publicacao_vinculada": "linked_publication", "descricao": "description",
    }),
    "especimes": ("specimens", {
        "codigo_etiqueta": "catalog_number", "grupo_insetos": "insect_order", "familia": "family", "especie": "species",
        "data_coleta": "collection_date", "local_coleta": "locality", "altitude_m": "elevation_m", "sexo": "sex",
        "estagio": "life_stage", "imagem_arquivo": "image_file", "fotografia_url": "photo_url", "notas": "notes",
        "projeto_id": "project_id", "determinador": "identified_by", "data_determinacao": "identification_date",
        "metodo_coleta": "sampling_method", "coletor": "collector", "numero_campo": "field_number",
        "localizacao_fisica": "storage_location", "emprestimo_situacao": "loan_status",
        "emprestimo_para": "loaned_to", "emprestimo_data": "loan_date", "notas_internas": "internal_notes",
    }),
    "medidas": ("measurements", {"especime_id": "specimen_id", "traco": "trait", "valor": "value", "unidade": "unit"}),
    "medicoes": ("legacy_measurements", {
        "especime_id": "specimen_id", "tamanho_chifre_mm": "horn_length_mm", "largura_pronoto_mm": "pronotum_width_mm",
    }),
    "usuarios": ("users", {"senha": "password_hash"}),
    "taxons": ("taxa", {
        "nome_informado": "queried_name", "situacao": "status", "sugestao": "suggestion", "chave_gbif": "gbif_key",
        "familia": "family", "ordem": "order_name", "consultado_em": "queried_at",
    }),
}


# renames the old Portuguese tables and columns in place, keeping all the data
def rename_legacy_schema():
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        renamed_taxa = False
        for old_table, (new_table, columns) in LEGACY_SCHEMA.items():
            if old_table in tables and new_table not in tables:
                conn.execute(text(f"ALTER TABLE {old_table} RENAME TO {new_table}"))
                tables.add(new_table)
                renamed_taxa = renamed_taxa or new_table == "taxa"
            if new_table not in tables:
                continue
            existing = {c["name"] for c in inspect(conn).get_columns(new_table)}
            for old_column, new_column in columns.items():
                if old_column in existing and new_column not in existing:
                    conn.execute(text(f"ALTER TABLE {new_table} RENAME COLUMN {old_column} TO {new_column}"))
        # the cache stored the old Portuguese status names; it is only a cache, so it is refilled from GBIF
        if renamed_taxa:
            conn.execute(text("DELETE FROM taxa"))


# adds new columns to databases created by older versions (SQLite or PostgreSQL)
def add_missing_columns():
    new_columns = {
        "specimens": [
            ("family", "VARCHAR"), ("elevation_m", "FLOAT"), ("sex", "VARCHAR"),
            ("life_stage", "VARCHAR"), ("image_file", "VARCHAR"),
            ("identified_by", "VARCHAR"), ("identification_date", "DATE"), ("sampling_method", "VARCHAR"),
            ("habitat", "VARCHAR"), ("collector", "VARCHAR"), ("field_number", "VARCHAR"),
            ("storage_location", "VARCHAR"), ("loan_status", "VARCHAR"),
            ("loaned_to", "VARCHAR"), ("loan_date", "DATE"), ("internal_notes", "VARCHAR"),
        ],
        "projects": [("description", "VARCHAR")],
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in new_columns.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, column_type in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))


# copies the old fixed measurements (pronotum and horn) into the per-trait measurements table
# only runs the first time the new table appears
def migrate_legacy_measurements(tables_before: set):
    if "measurements" in tables_before or "legacy_measurements" not in tables_before:
        return
    # trait names are data shown on the site, so they stay in Portuguese
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO measurements (specimen_id, trait, value, unit) "
            "SELECT specimen_id, 'Largura do pronoto', pronotum_width_mm, 'mm' FROM legacy_measurements "
            "WHERE pronotum_width_mm IS NOT NULL"
        ))
        conn.execute(text(
            "INSERT INTO measurements (specimen_id, trait, value, unit) "
            "SELECT specimen_id, 'Tamanho do chifre', horn_length_mm, 'mm' FROM legacy_measurements "
            "WHERE horn_length_mm IS NOT NULL"
        ))


# passwords stored as plain text by older versions are replaced by their hash
def migrate_plaintext_passwords():
    db = SessionLocal()
    try:
        for user in db.query(models.User).all():
            if not is_hash(user.password_hash):
                user.password_hash = hash_password(user.password_hash)
        db.commit()
    finally:
        db.close()


# creates missing tables and applies the migrations; safe to run many times
# called when the API starts and by the scripts (seed.py, create_admin.py), never on import
def initialize_database():
    rename_legacy_schema()
    tables_before = set(inspect(engine).get_table_names())
    models.Base.metadata.create_all(bind=engine)
    add_missing_columns()
    migrate_legacy_measurements(tables_before)
    migrate_plaintext_passwords()
