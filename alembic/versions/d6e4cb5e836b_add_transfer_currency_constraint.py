"""add transfer currency constraint

Revision ID: d6e4cb5e836b
Revises: a337437b6348
Create Date: 2026-09-29 13:24:40.213271

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e4cb5e836b'
down_revision: Union[str, Sequence[str], None] = 'a337437b6348'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_transfers_currency_format",
        "transfers",
        "currency ~ '^[A-Z]{3}$'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_transfers_currency_format",
        "transfers",
        type_="check",
    )