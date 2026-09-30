"""add account version constraint

Revision ID: a337437b6348
Revises: 3447ebb892e8
Create Date: 2026-09-29 09:19:29.029295

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a337437b6348'
down_revision: Union[str, Sequence[str], None] = '3447ebb892e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_accounts_version_non_negative",
        "accounts",
        "version >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_accounts_version_non_negative",
        "accounts",
        type_="check",
    )
