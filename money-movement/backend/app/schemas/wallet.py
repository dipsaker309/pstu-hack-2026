# pyright: reportMissingImports=false, reportMissingModuleSource=false
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class WalletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    balance: Decimal
