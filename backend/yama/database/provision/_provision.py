import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path
from urllib.parse import urlencode, urlunsplit

from sqlalchemy import URL, Dialect, text
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database import provision


class ProvisionError(Exception): ...


async def setup_database(
    database: str, /, *, migrate_executable: Path, connection: AsyncConnection
) -> None:
    if not await _database_exists(database, connection=connection):
        await _create_database(database, connection=connection)

    migrate_connection_url = _make_migrate_connection_url(
        database=database, sqlalchemy_connection_url=connection.engine.url
    )

    with _make_migrate_migrations_dir() as migrate_migrations_dir:
        await _upgrade_database(
            migrate_executable=migrate_executable,
            migrate_connection_url=migrate_connection_url,
            migrate_migrations_dir=migrate_migrations_dir,
        )


async def teardown_database(database: str, /, *, connection: AsyncConnection) -> None:
    if await _database_exists(database, connection=connection):
        await _drop_database(connection, database=database)


async def _database_exists(database: str, /, *, connection: AsyncConnection) -> bool:
    result = await connection.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :database"),
        {"database": database},
    )
    return result.first() is not None


async def _create_database(database: str, /, *, connection: AsyncConnection) -> None:
    quoted_database = _quote_identifier(database, dialect=connection.engine.dialect)
    await connection.execute(text(f"CREATE DATABASE {quoted_database}"))


async def _drop_database(connection: AsyncConnection, /, *, database: str) -> None:
    quoted_database = _quote_identifier(database, dialect=connection.engine.dialect)
    await connection.execute(text(f"DROP DATABASE {quoted_database}"))


async def _upgrade_database(
    *,
    migrate_executable: Path,
    migrate_connection_url: str,
    migrate_migrations_dir: Path,
) -> None:
    process = await asyncio.create_subprocess_exec(
        str(migrate_executable),
        "-database",
        migrate_connection_url,
        "-path",
        str(migrate_migrations_dir),
        "up",
    )
    await process.wait()

    if process.returncode != 0:
        raise ProvisionError("Database migration failed")


def _make_migrate_connection_url(
    *, database: str, sqlalchemy_connection_url: URL
) -> str:
    username = sqlalchemy_connection_url.username
    password = sqlalchemy_connection_url.password
    host = sqlalchemy_connection_url.host
    port = sqlalchemy_connection_url.port

    if username is None:
        raise ValueError("Username is required")
    if password is None:
        raise ValueError("Password is required")
    if host is None:
        raise ValueError("Host is required")
    if port is None:
        raise ValueError("Port is required")

    query = {
        "user": username,
        "password": password,
        "dbname": database,
        "sslmode": "disable",  # FIXME: Make SSL configurable
    }

    return urlunsplit(("postgresql", f"{host}:{port}", "/", urlencode(query), ""))


@contextmanager
def _make_migrate_migrations_dir() -> Iterator[Path]:
    with as_file(files(provision) / "migrations") as migrations_dir:
        yield migrations_dir


def _quote_identifier(identifier: str, /, *, dialect: Dialect) -> str:
    return dialect.identifier_preparer.quote(identifier)
