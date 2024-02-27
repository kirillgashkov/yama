import asyncio

from typer import Typer

from yama.db.connections import sqlalchemy_async_connection
from yama.db.provision.databases import setup_database, teardown_database
from yama.db.settings import Settings

app = Typer()


@app.command()
def up() -> None:
    async def f() -> None:
        settings = Settings()

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


@app.command()
def down() -> None:
    async def f() -> None:
        settings = Settings()

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