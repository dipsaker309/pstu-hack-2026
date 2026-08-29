# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MoneyRequestCreate(BaseModel):
    payer_username: str = Field(min_length=3, max_length=50)
    amount: Decimal = Field(gt=Decimal("0.00"), decimal_places=2, max_digits=15)
    note: str | None = Field(default=None, max_length=255)


class MoneyRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    payer_id: int
    amount: Decimal
    status: str
    note: str | None
    created_at: datetime
    updated_at: datetime
