# invitations
#
# Revision ID: 0005
# Revises: 0004
# Create Date: 2026-11-13
#
# Adds the invitations an admin sends by e-mail for someone to join a laboratory. Nothing that exists changes.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('laboratory_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('invited_by_id', sa.Integer(), nullable=False),
        sa.Column('code_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['laboratory_id'], ['laboratories.id']),
        sa.ForeignKeyConstraint(['invited_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('laboratory_id', 'email', name='uq_invitations_laboratory_id_email'),
    )
    op.create_index('ix_invitations_id', 'invitations', ['id'])
    op.create_index('ix_invitations_laboratory_id', 'invitations', ['laboratory_id'])
    op.create_index('ix_invitations_code_hash', 'invitations', ['code_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('invitations')
