import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Enum as SQLEnum,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AccountStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class Account(Base):
    __tablename__ = "accounts"

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="ck_accounts_balance_non_negative",
        ),
        CheckConstraint(
            "account_number ~ '^[0-9]{10}$'",
            name="ck_accounts_account_number_format",
        ),
        CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_accounts_currency_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    account_number: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
    )

    status: Mapped[AccountStatus] = mapped_column(
        SQLEnum(
            AccountStatus,
            name="accountstatus",
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="accounts",
    )

    sent_transfers = relationship(
        "Transfer",
        foreign_keys="Transfer.sender_account_id",
        back_populates="sender_account",
    )

    received_transfers = relationship(
        "Transfer",
        foreign_keys="Transfer.receiver_account_id",
        back_populates="receiver_account",
    )

    ledger_entries = relationship(
        "LedgerEntry",
        back_populates="account",
    )
