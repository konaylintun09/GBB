"""Async SQLAlchemy engine, session factory and declarative Base."""
import os
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# asyncpg + uvloop + SSL is broken inside Vercel's sandbox, so on serverless we force
# the psycopg (libpq) driver, which connects a different way and works there.
_ON_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _normalize_db_url(url: str):
    """Accept any standard Postgres URL and adapt it for the configured driver.

    Driver is chosen by settings.db_driver:
      - 'asyncpg'  -> postgresql+asyncpg://  (libpq-only params stripped; SSL via connect_args)
      - 'psycopg'  -> postgresql+psycopg://  (libpq handles sslmode/channel_binding natively)
    Non-Postgres URLs (e.g. sqlite) are returned unchanged.
    """
    driver = (settings.db_driver or "asyncpg").strip().lower()
    if _ON_SERVERLESS:
        driver = "psycopg"
    connect_args: dict = {}

    # strip any driver already present, normalise to bare postgresql://
    for pref in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql+psycopg2://"):
        if url.startswith(pref):
            url = "postgresql://" + url[len(pref):]
            break
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if not url.startswith("postgresql://"):
        return url, connect_args, driver  # sqlite/other — leave exactly as-is

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))

    if driver == "psycopg":
        scheme = "postgresql+psycopg"          # libpq understands sslmode/channel_binding — keep them
    else:
        scheme = "postgresql+asyncpg"
        ssl_needed = False
        for key in ("sslmode", "ssl", "channel_binding"):
            val = query.pop(key, None)          # asyncpg rejects these libpq params
            if val and str(val).lower() in ("require", "verify-ca", "verify-full", "prefer", "allow", "true", "1"):
                ssl_needed = True
        if ssl_needed:
            connect_args["ssl"] = True

    url = urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url, connect_args, driver


_raw_url = settings.database_url
# On serverless with NO external database configured, fall back to a throwaway SQLite
# file in /tmp so a demo works with zero setup. (Data resets when the function idles.)
if _ON_SERVERLESS and (not os.environ.get("DATABASE_URL") or "@db:5432" in _raw_url):
    _raw_url = "sqlite+aiosqlite:////tmp/flowea_demo.db"

_db_url, _connect_args, ACTIVE_DRIVER = _normalize_db_url(_raw_url)
IS_SQLITE = _db_url.startswith("sqlite")
if IS_SQLITE:
    ACTIVE_DRIVER = "sqlite"
engine = create_async_engine(_db_url, echo=False, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables if they do not exist (MVP bootstrap; use Alembic in production)."""
    from app import models  # noqa: F401 — register mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
