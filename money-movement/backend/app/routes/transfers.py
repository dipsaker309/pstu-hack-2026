# pyright: reportMissingImports=false, reportMissingModuleSource=false
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transfer import TransactionRead, TransferCreate
from app.services.money import create_transfer, list_transactions_for_user

router = APIRouter(prefix="/api/transfers", tags=["transfers"])


@router.post("", response_model=TransactionRead)
def send_money(
    payload: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Transaction:
    return create_transfer(
        db=db,
        sender=current_user,
        receiver_identifier=payload.receiver_username,
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
        note=payload.note,
    )


@router.get("/history", response_model=list[TransactionRead])
def transaction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    return list_transactions_for_user(db, current_user.id)
