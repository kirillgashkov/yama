from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from yama import file, user
from yama.database.config import Config as DatabaseSettings
from yama.database.utils import sqlalchemy_async_engine
from yama.file.config import Config as FileSettings
from yama.file.driver.config import Config as FileDriverSettings
from yama.user import auth
from yama.user.auth.config import Config as UserAuthSettings
from yama.user.config import Config as UserSettings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    database_settings = DatabaseSettings()  # pyright: ignore[reportCallIssue]
    file_settings = FileSettings()  # pyright: ignore[reportCallIssue]
    file_driver_settings = FileDriverSettings()  # pyright: ignore[reportCallIssue]
    user_settings = UserSettings()  # pyright: ignore[reportCallIssue]
    user_auth_settings = UserAuthSettings()  # pyright: ignore[reportCallIssue]

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
            "file_driver_settings": file_driver_settings,
            "user_settings": user_settings,
            "user_auth_settings": user_auth_settings,
        }


app = FastAPI(lifespan=lifespan)

app.include_router(auth.router)
app.include_router(file.router)
app.include_router(user.router)

for exception, handler in file.exception_handlers:
    app.add_exception_handler(exception, handler)  # type: ignore[arg-type]  # https://github.com/encode/starlette/discussions/2391, https://github.com/encode/starlette/pull/2403


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def get_health() -> Health:
    return Health(status="ok")
