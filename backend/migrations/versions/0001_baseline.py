# baseline: the schema as it was when Alembic was adopted
#
# Revision ID: 0001
# Revises:
# Create Date: 2026-11-11
#
# Databases created by earlier versions of the API already have these tables, without any Alembic record.
# So this revision only creates what is missing (tables and indexes) instead of failing on what exists:
# a new database gets everything, and an existing one is simply adopted and marked as being at this revision.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def create_table_if_missing(name, *columns):
    if name not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(name, *columns)


def create_index_if_missing(table, name, columns, unique=False):
    # a fresh inspector each time: the table may have been created a moment ago
    if name not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}:
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    create_table_if_missing(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('insect_group', sa.String(), nullable=False),
        sa.Column('measured_traits', sa.String(), nullable=True),
        sa.Column('locality', sa.String(), nullable=True),
        sa.Column('cover_url', sa.String(), nullable=True),
        sa.Column('dataset_url', sa.String(), nullable=True),
        sa.Column('finished', sa.Boolean(), nullable=True),
        sa.Column('linked_publication', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    create_index_if_missing('projects', 'ix_projects_id', ['id'])
    create_index_if_missing('projects', 'ix_projects_insect_group', ['insect_group'])
    create_index_if_missing('projects', 'ix_projects_title', ['title'])
    create_index_if_missing('projects', 'ix_projects_year', ['year'])

    create_table_if_missing(
        'taxa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queried_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('suggestion', sa.String(), nullable=True),
        sa.Column('gbif_key', sa.Integer(), nullable=True),
        sa.Column('family', sa.String(), nullable=True),
        sa.Column('order_name', sa.String(), nullable=True),
        sa.Column('queried_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    create_index_if_missing('taxa', 'ix_taxa_id', ['id'])
    create_index_if_missing('taxa', 'ix_taxa_queried_name', ['queried_name'], unique=True)

    create_table_if_missing(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    create_index_if_missing('users', 'ix_users_email', ['email'], unique=True)
    create_index_if_missing('users', 'ix_users_id', ['id'])

    create_table_if_missing(
        'specimens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('catalog_number', sa.String(), nullable=False),
        sa.Column('insect_order', sa.String(), nullable=False),
        sa.Column('family', sa.String(), nullable=True),
        sa.Column('species', sa.String(), nullable=False),
        sa.Column('collection_date', sa.Date(), nullable=True),
        sa.Column('locality', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('elevation_m', sa.Float(), nullable=True),
        sa.Column('sex', sa.String(), nullable=True),
        sa.Column('life_stage', sa.String(), nullable=True),
        sa.Column('image_file', sa.String(), nullable=True),
        sa.Column('photo_url', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('identified_by', sa.String(), nullable=True),
        sa.Column('identification_date', sa.Date(), nullable=True),
        sa.Column('sampling_method', sa.String(), nullable=True),
        sa.Column('habitat', sa.String(), nullable=True),
        sa.Column('collector', sa.String(), nullable=True),
        sa.Column('field_number', sa.String(), nullable=True),
        sa.Column('storage_location', sa.String(), nullable=True),
        sa.Column('loan_status', sa.String(), nullable=True),
        sa.Column('loaned_to', sa.String(), nullable=True),
        sa.Column('loan_date', sa.Date(), nullable=True),
        sa.Column('internal_notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    create_index_if_missing('specimens', 'ix_specimens_catalog_number', ['catalog_number'], unique=True)
    create_index_if_missing('specimens', 'ix_specimens_family', ['family'])
    create_index_if_missing('specimens', 'ix_specimens_id', ['id'])
    create_index_if_missing('specimens', 'ix_specimens_insect_order', ['insect_order'])
    create_index_if_missing('specimens', 'ix_specimens_species', ['species'])

    create_table_if_missing(
        'legacy_measurements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('specimen_id', sa.Integer(), nullable=False),
        sa.Column('horn_length_mm', sa.Float(), nullable=True),
        sa.Column('pronotum_width_mm', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['specimen_id'], ['specimens.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    create_index_if_missing('legacy_measurements', 'ix_legacy_measurements_id', ['id'])

    create_table_if_missing(
        'measurements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('specimen_id', sa.Integer(), nullable=False),
        sa.Column('trait', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['specimen_id'], ['specimens.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    create_index_if_missing('measurements', 'ix_measurements_id', ['id'])
    create_index_if_missing('measurements', 'ix_measurements_specimen_id', ['specimen_id'])


# going back past the baseline deletes every table and all of its data
def downgrade() -> None:
    for table in ('measurements', 'legacy_measurements', 'specimens', 'users', 'taxa', 'projects'):
        op.drop_table(table)
