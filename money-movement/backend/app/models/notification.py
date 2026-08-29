# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class NotificationType(StrEnum):
    TRANSFER_SENT = "TRANSFER_SENT"
    TRANSFER_RECEIVED = "TRANSFER_RECEIVED"
    MONEY_REQUEST_CREATED = "MONEY_REQUEST_CREATED"
    MONEY_REQUEST_ACCEPTED = "MONEY_REQUEST_ACCEPTED"
    MONEY_REQUEST_REJECTED = "MONEY_REQUEST_REJECTED"


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        Index("ix_notifications_status_created_at", "status", "created_at"),
        Index("ix_notifications_user_status_created_at", "user_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="notifications",
    )
