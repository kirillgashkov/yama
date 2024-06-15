from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from starlette.requests import Request


class BaseTable(DeclarativeBase): ...


@asynccontextmanager
async def make_engine(
    *, host: str, port: int, username: str, password: str, database: str
) -> AsyncIterator[AsyncEngine]:
    url = _make_connection_url(
        host=host, port=port, username=username, password=password, database=database
    )
    engine = create_async_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


@asynccontextmanager
async def make_connection(
    *, host: str, port: int, username: str, password: str, database: str
) -> AsyncIterator[AsyncConnection]:
    async with make_engine(
        host=host, port=port, username=username, password=password, database=database
    ) as engine:
        async with engine.connect() as conn:
            yield conn


def _make_connection_url(
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


def _get_engine(*, request: Request) -> AsyncEngine:
    """A lifetime dependency."""
    return request.state.engine  # type: ignore[no-any-return]


async def get_connection(
    *, engine: Annotated[AsyncEngine, Depends(_get_engine)]
) -> AsyncIterator[AsyncConnection]:
    """A dependency."""
    async with engine.connect() as connection:
        yield connection
