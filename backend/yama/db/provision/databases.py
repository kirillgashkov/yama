import asyncio
from pathlib import Path
from urllib.parse import urlencode, urlunsplit

from sqlalchemy import URL, Dialect, text
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseProvisionError(Exception):
    ...


def _quoted_identifier(identifier: str, *, dialect: Dialect) -> str:
    return dialect.identifier_preparer.quote(identifier)


# FIXME: Make SSL configurable
# HACK: `host` and `port` aren't validated
def _migrate_connection_url_from_sqlalchemy_connection_url(url: URL) -> str:
    if url.username is None:
        raise ValueError("Connection URL must contain a username")
    if url.password is None:
        raise ValueError("Connection URL must contain a password")
    if url.database is None:
        raise ValueError("Connection URL must contain a database name")
    if url.host is None:
        raise ValueError("Connection URL must contain a host")
    if url.port is None:
        raise ValueError("Connection URL must contain a port")

    query = {
        "user": url.username,
        "password": url.password,
        "dbname": url.database,
        "sslmode": "disable",
    }

    return urlunsplit(
        ("postgresql", f"{url.host}:{url.port}", "/", urlencode(query), "")
    )


async def database_exists(conn: AsyncConnection, *, database_name: str) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
        {"database_name": database_name},
    )
    return (await result.first()) is not None


async def create_database(conn: AsyncConnection, *, database_name: str) -> None:
    quoted_database_name = _quoted_identifier(
        database_name, dialect=conn.engine.dialect
    )
    await conn.execute(text(f"CREATE DATABASE {quoted_database_name}"))


async def drop_database(conn: AsyncConnection, *, database_name: str) -> None:
    quoted_database_name = _quoted_identifier(
        database_name, dialect=conn.engine.dialect
    )
    await conn.execute(text(f"DROP DATABASE {quoted_database_name}"))


async def upgrade_database(
    conn: AsyncConnection,
    *,
    migrate_executable: Path,
    migrate_migrations_dir: Path,
) -> None:
    migrate_connection_url = _migrate_connection_url_from_sqlalchemy_connection_url(
        conn.engine.url
    )

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
