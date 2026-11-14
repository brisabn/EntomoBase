# session version
#
# Revision ID: 0009
# Revises: 0008
# Create Date: 2026-11-14
#
# Adds the number that goes inside each login token, so changing the password can end the sessions already
# open. Every account starts at 0, and the tokens given before this have no number, which counts as 0: nobody
# is signed out by the upgrade itself.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('session_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('session_version')
