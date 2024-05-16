import asyncio

import uvicorn
from typer import Typer

from yama.api.settings import Settings as APISettings
from yama.database.provision.settings import Settings as DatabaseProvisionSettings
from yama.database.provision.utils import setup_database, teardown_database
from yama.database.settings import Settings as DatabaseSettings
from yama.database.utils import sqlalchemy_async_connection

app = Typer()
database_app = Typer()
app.add_typer(database_app, name="database")


@app.command(name="api")
def handle_api() -> None:
    settings = APISettings()

    uvicorn.run(
        "yama.api.routes:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


@database_app.command(name="up")
def handle_database_up() -> None:
    async def f() -> None:
        database_settings = DatabaseSettings()
        database_provision_settings = DatabaseProvisionSettings()

        async with sqlalchemy_async_connection(
            host=database_settings.host,
            port=database_settings.port,
            username=database_provision_settings.username,
            password=database_provision_settings.password,
            database=database_provision_settings.database,
        ) as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            await setup_database(
                autocommit_conn,
                database=database_settings.database,
                migrate_executable=database_provision_settings.migrate_executable,
            )

    asyncio.run(f())


@database_app.command(name="down")
def handle_database_down() -> None:
    async def f() -> None:
        database_settings = DatabaseSettings()
        database_provision_settings = DatabaseProvisionSettings()

        async with sqlalchemy_async_connection(
            host=database_settings.host,
            port=database_settings.port,
            username=database_provision_settings.username,
            password=database_provision_settings.password,
            database=database_provision_settings.database,
        ) as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            await teardown_database(
                autocommit_conn, database=database_settings.database
            )

    asyncio.run(f())


if __name__ == "__main__":
    app()
