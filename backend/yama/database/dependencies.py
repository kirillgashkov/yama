from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


# get_engine is a lifetime dependency that provides an AsyncEngine created by the
# lifespan.
def get_engine(*, request: Request) -> AsyncEngine:
    return request.state.engine  # type: ignore[no-any-return]


async def get_connection(
    *, engine: Annotated[AsyncEngine, Depends(get_engine)]
) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as connection:
        yield connection
