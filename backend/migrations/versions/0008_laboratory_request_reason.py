# laboratory request reason
#
# Revision ID: 0008
# Revises: 0007
# Create Date: 2026-11-14
#
# The requests to open a laboratory (table of 0004) start being used: this adds what the platform administrator
# writes when refusing one. It starts empty; nothing that exists changes.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('laboratory_requests') as batch:
        batch.add_column(sa.Column('decision_reason', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('laboratory_requests') as batch:
        batch.drop_column('decision_reason')
