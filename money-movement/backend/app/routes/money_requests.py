# pyright: reportMissingImports=false, reportMissingModuleSource=false
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.money_request import MoneyRequest
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.money_request import MoneyRequestCreate, MoneyRequestRead
from app.schemas.transfer import TransactionRead
from app.services.money import (
    accept_money_request,
    create_money_request,
    list_money_requests_for_user,
    reject_money_request,
)

router = APIRouter(prefix="/api/money-requests", tags=["money requests"])


class AcceptMoneyRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)


@router.post("", response_model=MoneyRequestRead)
def request_money(
    payload: MoneyRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MoneyRequest:
    return create_money_request(
        db=db,
        requester=current_user,
        payer_identifier=payload.payer_username,
        amount=payload.amount,
        note=payload.note,
    )


@router.get("", response_model=list[MoneyRequestRead])
def money_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MoneyRequest]:
    return list_money_requests_for_user(db, current_user.id)


@router.post("/{money_request_id}/accept", response_model=TransactionRead)
def accept_request(
    money_request_id: int,
    payload: AcceptMoneyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Transaction:
    return accept_money_request(
        db=db,
        payer=current_user,
        money_request_id=money_request_id,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/{money_request_id}/reject", response_model=MoneyRequestRead)
def reject_request(
    money_request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MoneyRequest:
    return reject_money_request(db, current_user, money_request_id)
