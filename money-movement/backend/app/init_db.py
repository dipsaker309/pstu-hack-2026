# pyright: reportMissingImports=false, reportMissingModuleSource=false
from app.database import Base, engine
from app.demo_data import seed_demo_accounts
from app.models import MoneyRequest, Notification, Transaction, User, Wallet


def main() -> None:
    Base.metadata.create_all(bind=engine)
    seed_demo_accounts()
    print("Database schema and demo accounts are ready.")


if __name__ == "__main__":
    main()
