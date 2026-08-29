from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.money_request import MoneyRequest, MoneyRequestStatus
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.routes.wallets import get_wallet
from app.services.money import (
    accept_money_request,
    create_money_request,
    create_transfer,
    reject_money_request,
)


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeDb:
    def __init__(self, scalar_results=None, scalars_results=None, get_results=None):
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = list(scalars_results or [])
        self.get_results = list(get_results or [])
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.refreshed = []

    def scalar(self, statement):
        if not self.scalar_results:
            raise AssertionError(f"Unexpected scalar query: {statement}")

        return self.scalar_results.pop(0)

    def scalars(self, statement):
        if not self.scalars_results:
            raise AssertionError(f"Unexpected scalars query: {statement}")

        return FakeScalarResult(self.scalars_results.pop(0))

    def get(self, model, primary_key):
        if not self.get_results:
            raise AssertionError(f"Unexpected get query: {model}, {primary_key}")

        return self.get_results.pop(0)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, value):
        self.refreshed.append(value)


def user(user_id: int, username: str) -> User:
    return User(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
    )


def wallet(user_id: int, balance: str) -> Wallet:
    return Wallet(
        user_id=user_id,
        balance=Decimal(balance),
    )


def money_request(
    request_id: int,
    requester_id: int,
    payer_id: int,
    status: MoneyRequestStatus = MoneyRequestStatus.PENDING,
) -> MoneyRequest:
    return MoneyRequest(
        id=request_id,
        requester_id=requester_id,
        payer_id=payer_id,
        amount=Decimal("250.00"),
        status=status,
    )


def assert_http_error(error_info, status_code: int, detail: str) -> None:
    assert error_info.value.status_code == status_code
    assert error_info.value.detail == detail


def test_create_transfer_fails_when_recipient_is_missing():
    db = FakeDb(scalar_results=[None])
    sender = user(1, "dip")

    with pytest.raises(HTTPException) as error:
        create_transfer(
            db=db,
            sender=sender,
            receiver_identifier="missing",
            amount=Decimal("100.00"),
            idempotency_key="transfer-1",
        )

    assert_http_error(error, 404, "Recipient was not found")
    assert db.committed is False


def test_create_transfer_fails_for_self_transfer():
    sender = user(1, "dip")
    db = FakeDb(scalar_results=[sender, None])

    with pytest.raises(HTTPException) as error:
        create_transfer(
            db=db,
            sender=sender,
            receiver_identifier="dip",
            amount=Decimal("100.00"),
            idempotency_key="transfer-2",
        )

    assert_http_error(error, 400, "You cannot send money to yourself")
    assert db.committed is False


def test_create_transfer_fails_when_balance_is_insufficient():
    sender = user(1, "dip")
    receiver = user(2, "kafi")
    sender_wallet = wallet(sender.id, "50.00")
    receiver_wallet = wallet(receiver.id, "100000.00")
    db = FakeDb(
        scalar_results=[receiver, None],
        scalars_results=[[sender_wallet, receiver_wallet]],
    )

    with pytest.raises(HTTPException) as error:
        create_transfer(
            db=db,
            sender=sender,
            receiver_identifier="kafi",
            amount=Decimal("100.00"),
            idempotency_key="transfer-3",
        )

    assert_http_error(error, 400, "Insufficient balance")
    assert sender_wallet.balance == Decimal("50.00")
    assert receiver_wallet.balance == Decimal("100000.00")
    assert db.committed is False


def test_create_transfer_moves_balance_and_queues_notifications():
    sender = user(1, "dip")
    receiver = user(2, "kafi")
    sender_wallet = wallet(sender.id, "1000.00")
    receiver_wallet = wallet(receiver.id, "500.00")
    db = FakeDb(
        scalar_results=[receiver, None],
        scalars_results=[[sender_wallet, receiver_wallet]],
    )

    transaction = create_transfer(
        db=db,
        sender=sender,
        receiver_identifier="kafi",
        amount=Decimal("125.50"),
        idempotency_key="transfer-4",
    )

    assert isinstance(transaction, Transaction)
    assert transaction.sender_id == sender.id
    assert transaction.receiver_id == receiver.id
    assert sender_wallet.balance == Decimal("874.50")
    assert receiver_wallet.balance == Decimal("625.50")
    assert len(db.added) == 3
    assert db.committed is True


def test_create_transfer_returns_existing_transaction_for_duplicate_key():
    sender = user(1, "dip")
    receiver = user(2, "kafi")
    existing = Transaction(
        sender_id=sender.id,
        receiver_id=receiver.id,
        amount=Decimal("100.00"),
        idempotency_key="transfer-5",
    )
    db = FakeDb(scalar_results=[receiver, existing])

    transaction = create_transfer(
        db=db,
        sender=sender,
        receiver_identifier="kafi",
        amount=Decimal("100.00"),
        idempotency_key="transfer-5",
    )

    assert transaction is existing
    assert db.added == []
    assert db.committed is False


def test_create_money_request_fails_when_payer_is_missing():
    db = FakeDb(scalar_results=[None])
    requester = user(1, "dip")

    with pytest.raises(HTTPException) as error:
        create_money_request(
            db=db,
            requester=requester,
            payer_identifier="missing",
            amount=Decimal("100.00"),
        )

    assert_http_error(error, 404, "Payer was not found")
    assert db.committed is False


def test_create_money_request_fails_for_self_request():
    requester = user(1, "dip")
    db = FakeDb(scalar_results=[requester])

    with pytest.raises(HTTPException) as error:
        create_money_request(
            db=db,
            requester=requester,
            payer_identifier="dip",
            amount=Decimal("100.00"),
        )

    assert_http_error(error, 400, "You cannot request money from yourself")
    assert db.committed is False


def test_accept_money_request_fails_when_request_is_missing():
    payer = user(2, "kafi")
    db = FakeDb(scalar_results=[None, None])

    with pytest.raises(HTTPException) as error:
        accept_money_request(
            db=db,
            payer=payer,
            money_request_id=99,
            idempotency_key="accept-1",
        )

    assert_http_error(error, 404, "Money request was not found")
    assert db.committed is False


def test_accept_money_request_fails_for_wrong_payer():
    payer = user(2, "kafi")
    request = money_request(10, requester_id=1, payer_id=3)
    db = FakeDb(scalar_results=[None, request])

    with pytest.raises(HTTPException) as error:
        accept_money_request(
            db=db,
            payer=payer,
            money_request_id=request.id,
            idempotency_key="accept-2",
        )

    assert_http_error(error, 403, "Only the requested payer can accept this request")
    assert db.committed is False


def test_accept_money_request_fails_when_request_is_completed():
    payer = user(2, "kafi")
    request = money_request(
        10,
        requester_id=1,
        payer_id=payer.id,
        status=MoneyRequestStatus.ACCEPTED,
    )
    db = FakeDb(scalar_results=[None, request])

    with pytest.raises(HTTPException) as error:
        accept_money_request(
            db=db,
            payer=payer,
            money_request_id=request.id,
            idempotency_key="accept-3",
        )

    assert_http_error(error, 400, "Money request is already completed")
    assert db.committed is False


def test_reject_money_request_fails_for_wrong_payer():
    payer = user(2, "kafi")
    request = money_request(10, requester_id=1, payer_id=3)
    db = FakeDb(scalar_results=[request])

    with pytest.raises(HTTPException) as error:
        reject_money_request(db=db, payer=payer, money_request_id=request.id)

    assert_http_error(error, 403, "Only the requested payer can reject this request")
    assert db.committed is False


def test_reject_money_request_fails_when_request_is_completed():
    payer = user(2, "kafi")
    request = money_request(
        10,
        requester_id=1,
        payer_id=payer.id,
        status=MoneyRequestStatus.REJECTED,
    )
    db = FakeDb(scalar_results=[request])

    with pytest.raises(HTTPException) as error:
        reject_money_request(db=db, payer=payer, money_request_id=request.id)

    assert_http_error(error, 400, "Money request is already completed")
    assert db.committed is False


def test_get_wallet_fails_when_wallet_is_missing():
    current_user = user(1, "dip")
    db = FakeDb(scalar_results=[None])

    with pytest.raises(HTTPException) as error:
        get_wallet(current_user=current_user, db=db)

    assert_http_error(error, 404, "Wallet was not found")
