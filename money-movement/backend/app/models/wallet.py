# pyright: reportMissingImports=false, reportMissingModuleSource=false
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Wallet(Base):
    __tablename__ = "wallets"

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="check_wallet_balance_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("100000.00"),
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="wallet",
    )
