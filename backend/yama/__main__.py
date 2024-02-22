import asyncio

import uvicorn
from typer import Typer

from yama.api.settings import Settings as APISettings
from yama.database.connections import sqlalchemy_async_connection
from yama.database.provision.databases import setup_database, teardown_database
from yama.database.settings import Settings as DatabaseSettings

app = Typer()
database_app = Typer()
app.add_typer(database_app, name="database")


@app.command()
def api() -> None:
    settings = APISettings()

    uvicorn.run(
        "yama.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


@database_app.command()
def up() -> None:
    async def f() -> None:
        settings = DatabaseSettings()

        if settings.provision is None:
            raise ValueError("Provision settings are required")

        async with sqlalchemy_async_connection(
            host=settings.host,
            port=settings.port,
            username=settings.provision.username,
            password=settings.provision.password,
            database=settings.provision.database,
        ) as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            await setup_database(
                autocommit_conn,
                database=settings.database,
                migrate_executable=settings.provision.migrate_executable,
            )

    asyncio.run(f())


@database_app.command()
def down() -> None:
    async def f() -> None:
        settings = DatabaseSettings()

        if settings.provision is None:
            raise ValueError("Provision settings are required")

        async with sqlalchemy_async_connection(
            host=settings.host,
            port=settings.port,
            username=settings.provision.username,
            password=settings.provision.password,
            database=settings.provision.database,
        ) as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            await teardown_database(autocommit_conn, database=settings.database)

    asyncio.run(f())


if __name__ == "__main__":
    app()
