# multi laboratory data model
#
# Revision ID: 0002
# Revises: 0001
# Create Date: 2026-11-11
#
# Adds laboratories, memberships, the visibility of projects and the per-laboratory catalog number.
# Everything that already exists is moved into a first laboratory, so no data is lost.
# SQLite cannot add a NOT NULL column with no default or change a constraint in place, so a column is added
# empty, filled, and only then made NOT NULL (batch mode rebuilds the table behind the scenes).
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# the first laboratory, which receives all the existing data; written out here on purpose, because a
# migration must keep doing the same thing even after the application code changes
FIRST_LABORATORY = {
    "slug": "ufmg",
    "name": "EntomoBase UFMG",
    "institution": "UFMG",
    "collection_code": "EntomoBase",
    "license": "http://creativecommons.org/licenses/by/4.0/legalcode",
    "listed": True,
}


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        'laboratories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('institution', sa.String(), nullable=False),
        sa.Column('collection_code', sa.String(), nullable=False),
        sa.Column('license', sa.String(), nullable=False),
        sa.Column('listed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_laboratories_id', 'laboratories', ['id'])
    op.create_index('ix_laboratories_slug', 'laboratories', ['slug'], unique=True)
    bind.execute(
        sa.text("INSERT INTO laboratories (slug, name, institution, collection_code, license, listed) "
                "VALUES (:slug, :name, :institution, :collection_code, :license, :listed)"),
        FIRST_LABORATORY,
    )
    first_id = bind.execute(sa.text("SELECT id FROM laboratories WHERE slug = :slug"), {"slug": FIRST_LABORATORY["slug"]}).scalar_one()

    # users: a name, the platform administrator flag, and a membership in the first laboratory for whoever exists
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('name', sa.String(), nullable=True))
        batch.add_column(sa.Column('is_superadmin', sa.Boolean(), server_default=sa.false(), nullable=False))

    op.create_table(
        'memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('laboratory_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['laboratory_id'], ['laboratories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'laboratory_id', name='uq_memberships_user_id_laboratory_id'),
    )
    op.create_index('ix_memberships_id', 'memberships', ['id'])
    op.create_index('ix_memberships_user_id', 'memberships', ['user_id'])
    op.create_index('ix_memberships_laboratory_id', 'memberships', ['laboratory_id'])
    bind.execute(sa.text("INSERT INTO memberships (user_id, laboratory_id, role) SELECT id, :lab, 'admin' FROM users"), {"lab": first_id})

    # projects: first the new columns, empty
    with op.batch_alter_table('projects') as batch:
        batch.add_column(sa.Column('laboratory_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('visibility', sa.String(), server_default='private', nullable=False))
        batch.add_column(sa.Column('share_token', sa.String(), nullable=True))
    # ... then filled: everything goes to the first laboratory, and a finished project was public until now
    bind.execute(sa.text("UPDATE projects SET laboratory_id = :lab"), {"lab": first_id})
    bind.execute(sa.text("UPDATE projects SET visibility = 'public' WHERE finished = :yes"), {"yes": True})
    # ... and only then the constraints
    with op.batch_alter_table('projects') as batch:
        batch.alter_column('laboratory_id', existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key('fk_projects_laboratory_id', 'laboratories', ['laboratory_id'], ['id'])
        batch.create_index('ix_projects_laboratory_id', ['laboratory_id'])
        batch.create_index('ix_projects_share_token', ['share_token'], unique=True)

    # specimens: same three steps, and the catalog number stops being unique in the whole database
    with op.batch_alter_table('specimens') as batch:
        batch.add_column(sa.Column('laboratory_id', sa.Integer(), nullable=True))
    bind.execute(sa.text("UPDATE specimens SET laboratory_id = :lab"), {"lab": first_id})
    with op.batch_alter_table('specimens') as batch:
        batch.alter_column('laboratory_id', existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key('fk_specimens_laboratory_id', 'laboratories', ['laboratory_id'], ['id'])
        batch.drop_index('ix_specimens_catalog_number')
        batch.create_index('ix_specimens_catalog_number', ['catalog_number'], unique=False)
        batch.create_index('ix_specimens_laboratory_id', ['laboratory_id'])
        batch.create_unique_constraint('uq_specimens_laboratory_id_catalog_number', ['laboratory_id', 'catalog_number'])


# going back keeps the data, but fails if two laboratories ended up with the same catalog number
# (the old schema required it to be unique everywhere), and forgets laboratories, memberships and visibility
def downgrade() -> None:
    with op.batch_alter_table('specimens') as batch:
        batch.drop_constraint('uq_specimens_laboratory_id_catalog_number', type_='unique')
        batch.drop_index('ix_specimens_laboratory_id')
        batch.drop_index('ix_specimens_catalog_number')
        batch.create_index('ix_specimens_catalog_number', ['catalog_number'], unique=True)
        batch.drop_constraint('fk_specimens_laboratory_id', type_='foreignkey')
        batch.drop_column('laboratory_id')

    with op.batch_alter_table('projects') as batch:
        batch.drop_index('ix_projects_share_token')
        batch.drop_index('ix_projects_laboratory_id')
        batch.drop_constraint('fk_projects_laboratory_id', type_='foreignkey')
        batch.drop_column('share_token')
        batch.drop_column('visibility')
        batch.drop_column('laboratory_id')

    op.drop_table('memberships')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('is_superadmin')
        batch.drop_column('name')
    op.drop_table('laboratories')
