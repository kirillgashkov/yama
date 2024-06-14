from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from yama import auth, database, file, user

from ._router import router


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    database_config = database.Config()  # pyright: ignore[reportCallIssue]
    file_config = file.Config()  # pyright: ignore[reportCallIssue]
    user_config = user.Config()  # pyright: ignore[reportCallIssue]
    auth_config = auth.Config()  # pyright: ignore[reportCallIssue]

    async with database.make_engine(
        host=database_config.host,
        port=database_config.port,
        username=database_config.username,
        password=database_config.password,
        database=database_config.database,
    ) as engine:
        # These must not be accessed directly, they must
        # be accessed through lifetime dependencies.
        yield {
            "engine": engine,
            "file_config": file_config,
            "user_config": user_config,
            "auth_config": auth_config,
        }


app = FastAPI(lifespan=_lifespan)

app.include_router(router)
app.include_router(auth.router)
app.include_router(file.router)
app.include_router(user.router)

for exception, handler in file.exception_handlers:
    app.add_exception_handler(exception, handler)  # type: ignore[arg-type]  # https://github.com/encode/starlette/discussions/2391, https://github.com/encode/starlette/pull/2403
