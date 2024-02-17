import asyncio
from pathlib import Path
from urllib.parse import urlencode, urlunsplit

from sqlalchemy import URL, Dialect, text
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseProvisionError(Exception):
    ...


def _quoted_identifier(identifier: str, dialect: Dialect) -> str:
    return dialect.identifier_preparer.quote(identifier)


# FIXME: Make SSL configurable
# HACK: `host` and `port` aren't validated
def _migrate_connection_url(database_name: str, sqlalchemy_connection_url: URL) -> str:
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
        "dbname": database_name,
        "sslmode": "disable",
    }

    return urlunsplit(("postgresql", f"{host}:{port}", "/", urlencode(query), ""))


async def database_exists(conn: AsyncConnection, *, database_name: str) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
        {"database_name": database_name},
    )
    return result.first() is not None


async def create_database(conn: AsyncConnection, *, database_name: str) -> None:
    quoted_database_name = _quoted_identifier(database_name, conn.engine.dialect)
    await conn.execute(text(f"CREATE DATABASE {quoted_database_name}"))


async def drop_database(conn: AsyncConnection, *, database_name: str) -> None:
    quoted_database_name = _quoted_identifier(database_name, conn.engine.dialect)
    await conn.execute(text(f"DROP DATABASE {quoted_database_name}"))


async def upgrade_database(
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
        raise DatabaseProvisionError("Database migration failed")


async def setup_database(
    conn: AsyncConnection,
    *,
    database_name: str,
    migrate_executable: Path,
    migrate_migrations_dir: Path,
) -> None:
    if not await database_exists(conn, database_name=database_name):
        await create_database(conn, database_name=database_name)

    migrate_connection_url = _migrate_connection_url(database_name, conn.engine.url)

    await upgrade_database(
        migrate_executable=migrate_executable,
        migrate_connection_url=migrate_connection_url,
        migrate_migrations_dir=migrate_migrations_dir,
    )


async def teardown_database(conn: AsyncConnection, *, database_name: str) -> None:
    if await database_exists(conn, database_name=database_name):
        await drop_database(conn, database_name=database_name)
