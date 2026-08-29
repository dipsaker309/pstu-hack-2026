# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.money_request import MoneyRequest
    from app.models.user import User


class TransactionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TransactionType(StrEnum):
    TRANSFER = "TRANSFER"
    REQUEST_PAYMENT = "REQUEST_PAYMENT"


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_transactions_idempotency_key",
        ),
        Index("ix_transactions_sender_created_at", "sender_id", "created_at"),
        Index("ix_transactions_receiver_created_at", "receiver_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    money_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("money_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status"),
        nullable=False,
        default=TransactionStatus.SUCCESS,
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"),
        nullable=False,
        default=TransactionType.TRANSFER,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sender: Mapped["User"] = relationship(
        "User",
        back_populates="sent_transactions",
        foreign_keys=[sender_id],
    )

    receiver: Mapped["User"] = relationship(
        "User",
        back_populates="received_transactions",
        foreign_keys=[receiver_id],
    )

    money_request: Mapped["MoneyRequest | None"] = relationship(
        "MoneyRequest",
        back_populates="transaction",
    )
