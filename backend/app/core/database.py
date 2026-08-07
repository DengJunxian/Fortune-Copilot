from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def _ensure_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url in {"sqlite://", "sqlite:///:memory:"}:
        return
    raw_path = database_url.removeprefix(prefix)
    path = Path("/" + raw_path.lstrip("/")) if raw_path.startswith("/") else Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str) -> Engine:
    _ensure_sqlite_parent(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_options: dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        engine_options["poolclass"] = StaticPool
    target = create_engine(database_url, **engine_options)
    if database_url.startswith("sqlite"):

        @event.listens_for(target, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: SQLiteConnection, _connection_record: object
        ) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return target


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database(target: Engine = engine) -> tuple[str, str]:
    try:
        with target.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok", "database connection available"
    except Exception:
        return "degraded", "database connection unavailable"
