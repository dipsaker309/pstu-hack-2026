# pyright: reportMissingImports=false, reportMissingModuleSource=false
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.models import MoneyRequest, Transaction, User, Wallet
from app.routes import auth_router, money_requests_router, transfers_router, wallets_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    yield


STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Money Movement API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(wallets_router)
app.include_router(transfers_router)
app.include_router(money_requests_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }
