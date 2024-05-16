from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


@asynccontextmanager
async def make_sqlalchemy_async_engine(
    *, host: str, port: int, username: str, password: str, database: str
) -> AsyncIterator[AsyncEngine]:
    url = _make_sqlalchemy_connection_url(
        host=host, port=port, username=username, password=password, database=database
    )
    engine = create_async_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


@asynccontextmanager
async def make_sqlalchemy_async_connection(
    *, host: str, port: int, username: str, password: str, database: str
) -> AsyncIterator[AsyncConnection]:
    async with make_sqlalchemy_async_engine(
        host=host, port=port, username=username, password=password, database=database
    ) as engine:
        async with engine.connect() as conn:
            yield conn


def _make_sqlalchemy_connection_url(
    *, host: str, port: int, username: str, password: str, database: str
) -> URL:
    return URL.create(
        drivername="postgresql+asyncpg",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )
