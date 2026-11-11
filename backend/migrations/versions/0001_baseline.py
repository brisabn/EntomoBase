# baseline: the first version of the schema
#
# Revision ID: 0001
# Revises:
# Create Date: 2026-11-11 16:08:18.326831
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('projects',
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
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_projects_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_projects_insect_group'), ['insect_group'], unique=False)
        batch_op.create_index(batch_op.f('ix_projects_title'), ['title'], unique=False)
        batch_op.create_index(batch_op.f('ix_projects_year'), ['year'], unique=False)

    op.create_table('taxa',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('queried_name', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('suggestion', sa.String(), nullable=True),
    sa.Column('gbif_key', sa.Integer(), nullable=True),
    sa.Column('family', sa.String(), nullable=True),
    sa.Column('order_name', sa.String(), nullable=True),
    sa.Column('queried_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('taxa', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_taxa_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_taxa_queried_name'), ['queried_name'], unique=True)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)

    op.create_table('specimens',
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
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('specimens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_specimens_catalog_number'), ['catalog_number'], unique=True)
        batch_op.create_index(batch_op.f('ix_specimens_family'), ['family'], unique=False)
        batch_op.create_index(batch_op.f('ix_specimens_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_specimens_insect_order'), ['insect_order'], unique=False)
        batch_op.create_index(batch_op.f('ix_specimens_species'), ['species'], unique=False)

    op.create_table('measurements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('specimen_id', sa.Integer(), nullable=False),
    sa.Column('trait', sa.String(), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['specimen_id'], ['specimens.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('measurements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_measurements_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_measurements_specimen_id'), ['specimen_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('measurements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_measurements_specimen_id'))
        batch_op.drop_index(batch_op.f('ix_measurements_id'))

    op.drop_table('measurements')
    with op.batch_alter_table('specimens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_specimens_species'))
        batch_op.drop_index(batch_op.f('ix_specimens_insect_order'))
        batch_op.drop_index(batch_op.f('ix_specimens_id'))
        batch_op.drop_index(batch_op.f('ix_specimens_family'))
        batch_op.drop_index(batch_op.f('ix_specimens_catalog_number'))

    op.drop_table('specimens')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_id'))
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    with op.batch_alter_table('taxa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_taxa_queried_name'))
        batch_op.drop_index(batch_op.f('ix_taxa_id'))

    op.drop_table('taxa')
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_year'))
        batch_op.drop_index(batch_op.f('ix_projects_title'))
        batch_op.drop_index(batch_op.f('ix_projects_insect_group'))
        batch_op.drop_index(batch_op.f('ix_projects_id'))

    op.drop_table('projects')
