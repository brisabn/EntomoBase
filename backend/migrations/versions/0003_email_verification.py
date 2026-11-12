# e-mail verification
#
# Revision ID: 0003
# Revises: 0002
# Create Date: 2026-11-11
#
# Adds the moment a user confirmed their e-mail address and the table of confirmation codes.
# The users that already exist were created by the platform administrator, so they count as confirmed.
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))

    users = sa.table('users', sa.column('email_verified_at', sa.DateTime()))
    op.get_bind().execute(sa.update(users).values(email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None)))

    op.create_table(
        'email_confirmations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_confirmations_id', 'email_confirmations', ['id'])
    op.create_index('ix_email_confirmations_user_id', 'email_confirmations', ['user_id'])
    op.create_index('ix_email_confirmations_code_hash', 'email_confirmations', ['code_hash'], unique=True)


# going back forgets who had confirmed their address and any pending codes
def downgrade() -> None:
    op.drop_table('email_confirmations')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('email_verified_at')
