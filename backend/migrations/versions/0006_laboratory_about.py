# laboratory presentation
#
# Revision ID: 0006
# Revises: 0005
# Create Date: 2026-11-13
#
# Adds what the About page of a laboratory shows: a presentation, a public contact e-mail and the team.
# All of them start empty; nothing that exists changes.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('laboratories') as batch:
        batch.add_column(sa.Column('about', sa.String(), nullable=True))
        batch.add_column(sa.Column('contact_email', sa.String(), nullable=True))
        batch.add_column(sa.Column('team', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('laboratories') as batch:
        batch.drop_column('team')
        batch.drop_column('contact_email')
        batch.drop_column('about')
