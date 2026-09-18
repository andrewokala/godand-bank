import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Enum as SQLEnum,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class LedgerDirection(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_ledger_entries_amount_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transfers.id"),
        nullable=False,
        index=True,
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    direction: Mapped[LedgerDirection] = mapped_column(
        SQLEnum(
            LedgerDirection,
            name="ledgerdirection",
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    transfer = relationship(
        "Transfer",
        back_populates="ledger_entries",
    )

    account = relationship(
        "Account",
        back_populates="ledger_entries",
    )
