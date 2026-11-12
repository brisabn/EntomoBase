# laboratory requests
#
# Revision ID: 0004
# Revises: 0003
# Create Date: 2026-11-12
#
# Adds the requests to open a laboratory. Nothing that exists changes.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'laboratory_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('institution', sa.String(), nullable=False),
        sa.Column('collection_code', sa.String(), nullable=False),
        sa.Column('license', sa.String(), nullable=True),
        sa.Column('message', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by_id', sa.Integer(), nullable=True),
        sa.Column('laboratory_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id']),
        sa.ForeignKeyConstraint(['decided_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['laboratory_id'], ['laboratories.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_laboratory_requests_id', 'laboratory_requests', ['id'])
    op.create_index('ix_laboratory_requests_requester_id', 'laboratory_requests', ['requester_id'])
    op.create_index('ix_laboratory_requests_slug', 'laboratory_requests', ['slug'])


def downgrade() -> None:
    op.drop_table('laboratory_requests')
