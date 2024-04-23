from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from yama.database.connections import sqlalchemy_async_engine
from yama.database.settings import Settings as DatabaseSettings
from yama.file.routes import router as file_router
from yama.file.settings import Settings as FileSettings
from yama.security.routes import router as security_router
from yama.users.routes import router as user_router
from yama.users.settings import Settings as UserSettings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    database_settings = DatabaseSettings()  # pyright: ignore[reportCallIssue]
    file_settings = FileSettings()  # pyright: ignore[reportCallIssue]
    user_settings = UserSettings()  # pyright: ignore[reportCallIssue]

    async with sqlalchemy_async_engine(
        host=database_settings.host,
        port=database_settings.port,
        username=database_settings.username,
        password=database_settings.password,
        database=database_settings.database,
    ) as engine:
        # These must not be accessed directly, they must
        # be accessed through lifetime dependencies
        yield {
            "engine": engine,
            "file_settings": file_settings,
            "user_settings": user_settings,
        }


app = FastAPI(lifespan=lifespan)
app.include_router(file_router)
app.include_router(security_router)
app.include_router(user_router)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def get_health() -> Health:
    return Health(status="ok")
