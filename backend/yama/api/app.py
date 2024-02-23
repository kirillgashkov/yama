from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from yama.database.connections import sqlalchemy_async_engine
from yama.database.settings import Settings as DatabaseSettings
from yama.users.routes import router as users_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    settings = DatabaseSettings()

    async with sqlalchemy_async_engine(
        host=settings.host,
        port=settings.port,
        username=settings.username,
        password=settings.password,
        database=settings.database,
    ) as engine:
        # `engine` must not be accessed directly, it must
        # be accessed through a lifetime dependency
        yield {"engine": engine}


app = FastAPI(lifespan=lifespan)
app.include_router(users_router)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def get_health() -> Health:
    return Health(status="ok")
