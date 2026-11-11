from sqlalchemy import inspect, text

from security import hash_password, is_hash

# One-time conversion of databases created before Alembic was adopted. Only databases that have tables but
# no alembic_version table go through here (see db_setup.initialize_database); a database that Alembic already
# manages never does. It brings the old data to the schema of Alembic's first revision (0001_baseline), which
# then creates whatever is still missing. It works with plain SQL and fixed names, not with models.py, because
# it must keep doing the same thing even after the models change.

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

# columns added over time to tables that already existed
ADDED_COLUMNS = {
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


# renames the old Portuguese tables and columns in place, keeping all the data
def rename_legacy_schema(engine):
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


# adds the columns that older versions did not have yet
def add_missing_columns(engine):
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, column_type in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))


# the old tables kept indexes named after the Portuguese tables (ix_especimes_codigo_etiqueta);
# once the baseline has created the new ones (ix_specimens_catalog_number), the old ones are dropped
def drop_old_index_names(engine):
    prefixes = tuple(f"ix_{old_table}_" for old_table in LEGACY_SCHEMA)
    inspector = inspect(engine)
    with engine.begin() as conn:
        for _, (table, _columns) in LEGACY_SCHEMA.items():
            if table not in inspector.get_table_names():
                continue
            for index in inspector.get_indexes(table):
                if index["name"].startswith(prefixes):
                    conn.execute(text(f'DROP INDEX "{index["name"]}"'))


# copies the old fixed measurements (pronotum and horn) into the per-trait measurements table
# only when the per-trait table did not exist yet
def migrate_legacy_measurements(engine, tables_before: set):
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


# passwords stored as plain text by the first versions are replaced by their hash
def hash_plaintext_passwords(engine):
    with engine.begin() as conn:
        for user_id, stored in conn.execute(text("SELECT id, password_hash FROM users")).fetchall():
            if not is_hash(stored):
                conn.execute(text("UPDATE users SET password_hash = :hash WHERE id = :id"),
                             {"hash": hash_password(stored), "id": user_id})


# steps that must happen before Alembic's baseline: the old tables and columns get their current names
def prepare(engine):
    rename_legacy_schema(engine)
    add_missing_columns(engine)


# steps that need the baseline's tables to exist: data copies and cleanup
def finish(engine, tables_before: set):
    migrate_legacy_measurements(engine, tables_before)
    hash_plaintext_passwords(engine)
    drop_old_index_names(engine)
