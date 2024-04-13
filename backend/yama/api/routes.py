from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from yama.database.connections import sqlalchemy_async_engine
from yama.database.settings import Settings as DatabaseSettings
from yama.files.routes import router as files_router
from yama.files.settings import Settings as FilesSettings
from yama.security.routes import router as security_router
from yama.users.routes import router as users_router
from yama.users.settings import Settings as UsersSettings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    database_settings = DatabaseSettings()  # pyright: ignore[reportCallIssue]
    files_settings = FilesSettings()  # pyright: ignore[reportCallIssue]
    users_settings = UsersSettings()  # pyright: ignore[reportCallIssue]

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
            "files_settings": files_settings,
            "users_settings": users_settings,
        }


app = FastAPI(lifespan=lifespan)
app.include_router(files_router)
app.include_router(security_router)
app.include_router(users_router)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def get_health() -> Health:
    return Health(status="ok")
