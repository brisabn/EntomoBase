# visibility changes
#
# Revision ID: 0007
# Revises: 0006
# Create Date: 2026-11-13
#
# Adds the record of who changed who can see each project, and when. Nothing that exists changes; the record
# starts empty (the projects that already exist have no history before this).
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'visibility_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('laboratory_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('project_title', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_email', sa.String(), nullable=False),
        sa.Column('from_visibility', sa.String(), nullable=True),
        sa.Column('to_visibility', sa.String(), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['laboratory_id'], ['laboratories.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_visibility_changes_id', 'visibility_changes', ['id'])
    op.create_index('ix_visibility_changes_laboratory_id', 'visibility_changes', ['laboratory_id'])
    op.create_index('ix_visibility_changes_project_id', 'visibility_changes', ['project_id'])


def downgrade() -> None:
    op.drop_table('visibility_changes')
