from app.routes.auth import router as auth_router
from app.routes.money_requests import router as money_requests_router
from app.routes.transfers import router as transfers_router
from app.routes.wallets import router as wallets_router

__all__ = [
    "auth_router",
    "money_requests_router",
    "transfers_router",
    "wallets_router",
]
