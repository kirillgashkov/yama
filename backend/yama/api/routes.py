from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from yama.database.utils import sqlalchemy_async_engine
from yama.database.settings import Settings as DatabaseSettings
from yama.file.routes import files_file_error_handler
from yama.file.routes import router as file_router
from yama.file.settings import Settings as FileSettings
from yama.file.utils import FilesFileError
from yama.user.auth.routes import router as user_auth_router
from yama.user.routes import router as user_router
from yama.user.settings import Settings as UserSettings


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
app.include_router(user_auth_router)
app.include_router(user_router)

app.add_exception_handler(FilesFileError, files_file_error_handler)  # type: ignore  # https://github.com/encode/starlette/discussions/2391 and https://github.com/encode/starlette/pull/2403


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def get_health() -> Health:
    return Health(status="ok")
