import asyncio
from pathlib import Path

from sqlalchemy import text, Dialect
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseProvisionError(Exception):
    ...


def _quoted_identifier(identifier: str, *, dialect: Dialect) -> str:
    return dialect.identifier_preparer.quote(identifier)


async def database_exists(conn: AsyncConnection, *, database_name: str) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
        {"database_name": database_name},
    )
    return (await result.first()) is not None


async def create_database(
    autocommit_conn: AsyncConnection, *, database_name: str
) -> None:
    quoted_database_name = _quoted_identifier(
        database_name, dialect=autocommit_conn.engine.dialect
    )
    await autocommit_conn.execute(text(f"CREATE DATABASE {quoted_database_name}"))


async def drop_database(
    autocommit_conn: AsyncConnection, *, database_name: str
) -> None:
    quoted_database_name = _quoted_identifier(
        database_name, dialect=autocommit_conn.engine.dialect
    )
    await autocommit_conn.execute(text(f"DROP DATABASE {quoted_database_name}"))


async def upgrade_database(
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
