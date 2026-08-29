# pyright: reportMissingImports=false, reportMissingModuleSource=false
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.wallet import WalletRead

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("", response_model=WalletRead)
def get_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == current_user.id))

    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet was not found")

    return wallet
