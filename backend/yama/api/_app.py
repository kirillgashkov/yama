from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from yama import database, file, user
from yama.database.utils import make_sqlalchemy_async_engine
from yama.file import driver as file_driver
from yama.user import auth


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    database_settings = database.Config()  # pyright: ignore[reportCallIssue]
    file_settings = file.Config()  # pyright: ignore[reportCallIssue]
    file_driver_settings = file_driver.Config()  # pyright: ignore[reportCallIssue]
    user_settings = user.Config()  # pyright: ignore[reportCallIssue]
    user_auth_settings = auth.Config()  # pyright: ignore[reportCallIssue]

    async with make_sqlalchemy_async_engine(
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
