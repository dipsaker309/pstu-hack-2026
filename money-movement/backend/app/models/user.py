# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.money_request import MoneyRequest
    from app.models.notification import Notification
    from app.models.transaction import Transaction
    from app.models.wallet import Wallet


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
    )

    sent_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="sender",
        foreign_keys="Transaction.sender_id",
    )

    received_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="receiver",
        foreign_keys="Transaction.receiver_id",
    )

    outgoing_money_requests: Mapped[list["MoneyRequest"]] = relationship(
        "MoneyRequest",
        back_populates="requester",
        foreign_keys="MoneyRequest.requester_id",
    )

    incoming_money_requests: Mapped[list["MoneyRequest"]] = relationship(
        "MoneyRequest",
        back_populates="payer",
        foreign_keys="MoneyRequest.payer_id",
    )

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
    )
