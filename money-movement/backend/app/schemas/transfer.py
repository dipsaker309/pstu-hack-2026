# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransferCreate(BaseModel):
    receiver_username: str = Field(min_length=3, max_length=50)
    amount: Decimal = Field(gt=Decimal("0.00"), decimal_places=2, max_digits=15)
    idempotency_key: str = Field(min_length=8, max_length=100)
    note: str | None = Field(default=None, max_length=255)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    receiver_id: int
    amount: Decimal
    status: str
    transaction_type: str
    idempotency_key: str
    note: str | None
    created_at: datetime
