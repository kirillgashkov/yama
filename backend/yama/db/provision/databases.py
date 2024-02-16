import asyncio
from pathlib import Path

from sqlalchemy import text, Dialect
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseProvisionError(Exception):
    ...


def _quoted_identifier(identifier: str, *, dialect: Dialect) -> str:
    return dialect.identifier_preparer.quote(identifier)


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
    migrate_connection_uri: str,
    migrate_migrations_dir: Path,
) -> None:
    process = await asyncio.create_subprocess_exec(
        str(migrate_executable),
        "-database",
        migrate_connection_uri,
        "-path",
        str(migrate_migrations_dir),
        "up",
    )
    await process.wait()

    if process.returncode != 0:
        raise DatabaseProvisionError("Database migration failed")
