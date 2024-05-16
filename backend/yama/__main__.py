import asyncio
import sys

import uvicorn
from typer import Typer

from yama import api, database, function
from yama.database import provision
from yama.database.provision import setup_database, teardown_database
from yama.database.utils import make_sqlalchemy_async_connection

app = Typer()
database_app = Typer()
app.add_typer(database_app, name="database")


@app.command(name="api")
def handle_api() -> None:
    settings = api.Config()

    uvicorn.run(
        "yama.api:app", host=settings.host, port=settings.port, reload=settings.reload
    )


@database_app.command(name="up")
def handle_database_up() -> None:
    async def f() -> None:
        database_settings = database.Config()  # pyright: ignore[reportCallIssue]
        database_provision_settings = provision.Config()  # pyright: ignore[reportCallIssue]

        async with make_sqlalchemy_async_connection(
            host=database_settings.host,
            port=database_settings.port,
            username=database_provision_settings.username,
            password=database_provision_settings.password,
            database=database_provision_settings.database,
        ) as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            await setup_database(
                database_settings.database,
                migrate_executable=database_provision_settings.migrate_executable,
                connection=autocommit_conn,
            )

    asyncio.run(f())


@database_app.command(name="down")
def handle_database_down() -> None:
    async def f() -> None:
        database_settings = database.Config()  # pyright: ignore[reportCallIssue]
        database_provision_settings = provision.Config()  # pyright: ignore[reportCallIssue]

        async with make_sqlalchemy_async_connection(
            host=database_settings.host,
            port=database_settings.port,
            username=database_provision_settings.username,
            password=database_provision_settings.password,
            database=database_provision_settings.database,
        ) as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            await teardown_database(
                database_settings.database, connection=autocommit_conn
            )

    asyncio.run(f())


@app.command(name="function")
def handle_function(*, command: list[str]) -> None:
    async def f() -> None:
        function_in = function.FunctionIn.model_validate_json(sys.stdin.read())

        function_out = await function.execute(command, function_in=function_in)

        sys.stdout.write(function_out.model_dump_json())

    asyncio.run(f())


if __name__ == "__main__":
    app()
