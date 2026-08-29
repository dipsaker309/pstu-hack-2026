# pyright: reportMissingImports=false, reportMissingModuleSource=false
from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.security import hash_password

DEMO_USERS = [
    {
        "name": "Dip",
        "username": "dip",
        "email": "dip@example.com",
        "password": "Dip@12345",
    },
    {
        "name": "Kafi",
        "username": "kafi",
        "email": "kafi@example.com",
        "password": "Kafi@12345",
    },
]


def seed_demo_accounts() -> None:
    db = SessionLocal()

    try:
        for demo_user in DEMO_USERS:
            user = db.scalar(
                select(User).where(User.username == demo_user["username"]),
            )

            if user is None:
                user = User(
                    username=demo_user["username"],
                    email=demo_user["email"],
                    password_hash=hash_password(demo_user["password"]),
                )
                db.add(user)
                db.flush()
            else:
                user.email = demo_user["email"]
                user.password_hash = hash_password(demo_user["password"])

            wallet = db.scalar(select(Wallet).where(Wallet.user_id == user.id))

            if wallet is None:
                db.add(
                    Wallet(
                        user_id=user.id,
                        balance=Decimal("100000.00"),
                    ),
                )

        db.commit()
    finally:
        db.close()
