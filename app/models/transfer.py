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
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TransferStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"


class Transfer(Base):
    __tablename__ = "transfers"

    __table_args__ = (
        CheckConstraint(
            "sender_account_id <> receiver_account_id",
            name="ck_transfers_different_accounts",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_transfers_amount_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    sender_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    receiver_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[TransferStatus] = mapped_column(
        SQLEnum(
            TransferStatus,
            name="transferstatus",
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=TransferStatus.PENDING,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    sender_account = relationship(
        "Account",
        foreign_keys=[sender_account_id],
        back_populates="sent_transfers",
    )

    receiver_account = relationship(
        "Account",
        foreign_keys=[receiver_account_id],
        back_populates="received_transfers",
    )

    ledger_entries = relationship(
        "LedgerEntry",
        back_populates="transfer",
    )
