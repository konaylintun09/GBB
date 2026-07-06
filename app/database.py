"""Async SQLAlchemy engine, session factory and declarative Base."""
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _normalize_db_url(url: str):
    """Accept any standard Postgres URL (Render/Railway/Neon/Heroku) and adapt it for asyncpg.

    - postgres:// or postgresql:// -> postgresql+asyncpg://
    - strip libpq-only params (sslmode, channel_binding) that asyncpg rejects,
      turning an SSL requirement into asyncpg's connect_args={'ssl': True}.
    """
    connect_args: dict = {}
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    # only rewrite query params for postgres URLs; leave sqlite/others exactly as-is
    if not url.startswith("postgresql+asyncpg://"):
        return url, connect_args

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    ssl_needed = False
    for key in ("sslmode", "ssl", "channel_binding"):
        val = query.pop(key, None)
        if val and str(val).lower() in ("require", "verify-ca", "verify-full", "prefer", "allow", "true", "1"):
            ssl_needed = True
    if ssl_needed:
        connect_args["ssl"] = True
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url, connect_args


_db_url, _connect_args = _normalize_db_url(settings.database_url)
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
