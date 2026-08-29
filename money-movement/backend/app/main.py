# pyright: reportMissingImports=false, reportMissingModuleSource=false
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import Base, RUN_STARTUP_DB_INIT, SessionLocal, engine
from app.demo_data import seed_demo_accounts
from app.models import MoneyRequest, Notification, Transaction, User, Wallet
from app.routes import auth_router, money_requests_router, transfers_router, wallets_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if RUN_STARTUP_DB_INIT:
        Base.metadata.create_all(bind=engine)
        seed_demo_accounts()

    yield


STATIC_DIR = Path(__file__).resolve().parent / "static"
REQUEST_TOTALS: defaultdict[tuple[str, str, int], int] = defaultdict(int)
REQUEST_LATENCY_TOTALS: defaultdict[tuple[str, str], float] = defaultdict(float)
METRICS_LOCK = Lock()

app = FastAPI(
    title="Cresco API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(wallets_router)
app.include_router(transfers_router)
app.include_router(money_requests_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    started_at = perf_counter()
    response = await call_next(request)
    elapsed = perf_counter() - started_at
    path = request.url.path

    with METRICS_LOCK:
        REQUEST_TOTALS[(request.method, path, response.status_code)] += 1
        REQUEST_LATENCY_TOTALS[(request.method, path)] += elapsed

    return response


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "reachable",
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = [
        "# HELP cresco_http_requests_total Total HTTP requests handled by this API process.",
        "# TYPE cresco_http_requests_total counter",
    ]

    with METRICS_LOCK:
        for (method, path, status_code), count in sorted(REQUEST_TOTALS.items()):
            lines.append(
                'cresco_http_requests_total{'
                f'method="{method}",path="{path}",status_code="{status_code}"'
                f"}} {count}",
            )

        lines.extend(
            [
                "# HELP cresco_http_request_latency_seconds_total Total HTTP request latency by this API process.",
                "# TYPE cresco_http_request_latency_seconds_total counter",
            ],
        )

        for (method, path), seconds in sorted(REQUEST_LATENCY_TOTALS.items()):
            lines.append(
                'cresco_http_request_latency_seconds_total{'
                f'method="{method}",path="{path}"'
                f"}} {seconds:.6f}",
            )

    return "\n".join(lines) + "\n"
