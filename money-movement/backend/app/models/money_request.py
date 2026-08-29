# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class MoneyRequestStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MoneyRequest(Base):
    __tablename__ = "money_requests"

    __table_args__ = (
        Index("ix_money_requests_payer_status_created_at", "payer_id", "status", "created_at"),
        Index("ix_money_requests_requester_created_at", "requester_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    payer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    status: Mapped[MoneyRequestStatus] = mapped_column(
        Enum(MoneyRequestStatus, name="money_request_status"),
        nullable=False,
        default=MoneyRequestStatus.PENDING,
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    requester: Mapped["User"] = relationship(
        "User",
        back_populates="outgoing_money_requests",
        foreign_keys=[requester_id],
    )

    payer: Mapped["User"] = relationship(
        "User",
        back_populates="incoming_money_requests",
        foreign_keys=[payer_id],
    )

    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        back_populates="money_request",
        uselist=False,
    )
