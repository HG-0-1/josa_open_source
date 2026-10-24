"""SQLite setup for private journal data, stored outside the public frontend."""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _default_database_url() -> str:
    configured = os.getenv("MOTANAFAS_DATABASE_URL")
    if configured:
        return configured
    data_dir = Path.home() / ".local" / "share" / "motanafas"
    return f"sqlite:///{data_dir / 'journal.sqlite3'}"


def _make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine = _make_engine(_default_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure_database(url: str) -> None:
    """Replace the engine; used by isolated tests with temporary SQLite files."""
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_database() -> None:
    # Models register with Base when routers are imported by main.py.
    if engine.url.drivername.startswith("sqlite") and engine.url.database:
        database_path = Path(engine.url.database)
        database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    if engine.url.drivername.startswith("sqlite") and engine.url.database:
        database_path = Path(engine.url.database)
        if database_path.exists():
            try:
                database_path.chmod(0o600)
            except OSError:
                # Windows filesystems may not support POSIX mode changes.
                pass


async def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
