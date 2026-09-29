"""add failed login count constraint

Revision ID: 3447ebb892e8
Revises: b74c80ccaea6
Create Date: 2026-09-28 16:54:56.824544

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3447ebb892e8'
down_revision: Union[str, Sequence[str], None] = 'b74c80ccaea6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_users_failed_login_count_non_negative",
        "users",
        "failed_login_count >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_users_failed_login_count_non_negative",
        "users",
        type_="check",
    )