# pyright: reportMissingImports=false, reportMissingModuleSource=false
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def sqlite_file_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None

    raw_path = database_url.removeprefix("sqlite:///")
    db_path = Path(raw_path)

    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parents[1] / db_path

    return db_path


load_env_file()

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/money_movement"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine_options: dict[str, object] = {
    "pool_pre_ping": True,
}

db_path = sqlite_file_path(DATABASE_URL)

if db_path is not None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
        },
    )

RUN_STARTUP_DB_INIT = os.getenv("RUN_STARTUP_DB_INIT", "true").strip().lower() == "true"

engine = create_engine(
    DATABASE_URL,
    **engine_options,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
