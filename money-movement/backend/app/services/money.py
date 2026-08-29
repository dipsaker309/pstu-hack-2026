# pyright: reportMissingImports=false, reportMissingModuleSource=false
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.money_request import MoneyRequest, MoneyRequestStatus
from app.models.notification import NotificationType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.models.wallet import Wallet
from app.services.notifications import queue_notification


def find_user_by_identifier(db: Session, identifier: str) -> User | None:
    normalized = identifier.strip().lower()
    statement = select(User).where(
        or_(
            User.username == normalized,
            User.email == normalized,
        ),
    )
    return db.scalar(statement)


def list_transactions_for_user(db: Session, user_id: int) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(
            or_(
                Transaction.sender_id == user_id,
                Transaction.receiver_id == user_id,
            ),
        )
        .order_by(Transaction.created_at.desc())
    )
    return list(db.scalars(statement).all())


def _find_transaction_by_idempotency_key(
    db: Session,
    idempotency_key: str,
) -> Transaction | None:
    return db.scalar(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key),
    )


def _lock_wallets_for_transfer(
    db: Session,
    sender_id: int,
    receiver_id: int,
) -> tuple[Wallet, Wallet]:
    wallet_user_ids = sorted({sender_id, receiver_id})
    wallets = list(
        db.scalars(
            select(Wallet)
            .where(Wallet.user_id.in_(wallet_user_ids))
            .order_by(Wallet.user_id)
            .with_for_update(),
        ).all(),
    )
    wallet_by_user_id = {wallet.user_id: wallet for wallet in wallets}
    sender_wallet = wallet_by_user_id.get(sender_id)
    receiver_wallet = wallet_by_user_id.get(receiver_id)

    if sender_wallet is None or receiver_wallet is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet is missing for one of the users",
        )

    return sender_wallet, receiver_wallet


def _finish_transaction_commit(
    db: Session,
    transaction: Transaction,
    idempotency_key: str,
) -> Transaction:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = _find_transaction_by_idempotency_key(db, idempotency_key)

        if duplicate is not None:
            return duplicate

        raise

    db.refresh(transaction)
    return transaction


def _apply_transfer_to_user(
    db: Session,
    sender: User,
    receiver: User,
    amount: Decimal,
    idempotency_key: str,
    note: str | None = None,
    money_request: MoneyRequest | None = None,
    transaction_type: TransactionType = TransactionType.TRANSFER,
    commit: bool = True,
) -> Transaction:
    existing = _find_transaction_by_idempotency_key(db, idempotency_key)

    if existing is not None:
        return existing

    if sender.id == receiver.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot send money to yourself",
        )

    sender_wallet, receiver_wallet = _lock_wallets_for_transfer(
        db=db,
        sender_id=sender.id,
        receiver_id=receiver.id,
    )

    if sender_wallet.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )

    sender_wallet.balance -= amount
    receiver_wallet.balance += amount

    transaction = Transaction(
        sender_id=sender.id,
        receiver_id=receiver.id,
        money_request_id=money_request.id if money_request else None,
        amount=amount,
        transaction_type=transaction_type,
        idempotency_key=idempotency_key,
        note=note,
    )
    db.add(transaction)
    queue_notification(
        db=db,
        user_id=sender.id,
        notification_type=NotificationType.TRANSFER_SENT,
        message=f"Sent BDT {amount} to {receiver.username}",
    )
    queue_notification(
        db=db,
        user_id=receiver.id,
        notification_type=NotificationType.TRANSFER_RECEIVED,
        message=f"Received BDT {amount} from {sender.username}",
    )

    if commit:
        return _finish_transaction_commit(db, transaction, idempotency_key)

    return transaction


def create_transfer(
    db: Session,
    sender: User,
    receiver_identifier: str,
    amount: Decimal,
    idempotency_key: str,
    note: str | None = None,
    money_request: MoneyRequest | None = None,
    transaction_type: TransactionType = TransactionType.TRANSFER,
) -> Transaction:
    receiver = find_user_by_identifier(db, receiver_identifier)

    if receiver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient was not found",
        )

    return _apply_transfer_to_user(
        db=db,
        sender=sender,
        receiver=receiver,
        amount=amount,
        idempotency_key=idempotency_key,
        note=note,
        money_request=money_request,
        transaction_type=transaction_type,
        commit=True,
    )


def create_money_request(
    db: Session,
    requester: User,
    payer_identifier: str,
    amount: Decimal,
    note: str | None = None,
) -> MoneyRequest:
    payer = find_user_by_identifier(db, payer_identifier)

    if payer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payer was not found",
        )

    if payer.id == requester.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot request money from yourself",
        )

    money_request = MoneyRequest(
        requester_id=requester.id,
        payer_id=payer.id,
        amount=amount,
        note=note,
    )
    db.add(money_request)
    queue_notification(
        db=db,
        user_id=payer.id,
        notification_type=NotificationType.MONEY_REQUEST_CREATED,
        message=f"{requester.username} requested BDT {amount}",
    )
    db.commit()
    db.refresh(money_request)
    return money_request


def list_money_requests_for_user(db: Session, user_id: int) -> list[MoneyRequest]:
    statement = (
        select(MoneyRequest)
        .where(
            or_(
                MoneyRequest.requester_id == user_id,
                MoneyRequest.payer_id == user_id,
            ),
        )
        .order_by(MoneyRequest.created_at.desc())
    )
    return list(db.scalars(statement).all())


def accept_money_request(
    db: Session,
    payer: User,
    money_request_id: int,
    idempotency_key: str,
) -> Transaction:
    existing = _find_transaction_by_idempotency_key(db, idempotency_key)

    if existing is not None:
        return existing

    money_request = db.scalar(
        select(MoneyRequest)
        .where(MoneyRequest.id == money_request_id)
        .with_for_update(),
    )

    if money_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Money request was not found",
        )

    if money_request.payer_id != payer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requested payer can accept this request",
        )

    if money_request.status != MoneyRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Money request is already completed",
        )

    requester = db.get(User, money_request.requester_id)

    if requester is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requester was not found",
        )

    transaction = _apply_transfer_to_user(
        db=db,
        sender=payer,
        receiver=requester,
        amount=money_request.amount,
        idempotency_key=idempotency_key,
        note=money_request.note,
        money_request=money_request,
        transaction_type=TransactionType.REQUEST_PAYMENT,
        commit=False,
    )
    money_request.status = MoneyRequestStatus.ACCEPTED
    queue_notification(
        db=db,
        user_id=requester.id,
        notification_type=NotificationType.MONEY_REQUEST_ACCEPTED,
        message=f"{payer.username} paid your BDT {money_request.amount} request",
    )

    return _finish_transaction_commit(db, transaction, idempotency_key)


def reject_money_request(db: Session, payer: User, money_request_id: int) -> MoneyRequest:
    money_request = db.scalar(
        select(MoneyRequest)
        .where(MoneyRequest.id == money_request_id)
        .with_for_update(),
    )

    if money_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Money request was not found",
        )

    if money_request.payer_id != payer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requested payer can reject this request",
        )

    if money_request.status != MoneyRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Money request is already completed",
        )

    requester_id = money_request.requester_id
    money_request.status = MoneyRequestStatus.REJECTED
    queue_notification(
        db=db,
        user_id=requester_id,
        notification_type=NotificationType.MONEY_REQUEST_REJECTED,
        message=f"{payer.username} rejected your BDT {money_request.amount} request",
    )
    db.commit()
    db.refresh(money_request)
    return money_request
