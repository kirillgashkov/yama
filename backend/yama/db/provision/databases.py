import asyncio
from pathlib import Path
from typing import Any


class DatabaseProvisionError(Exception):
    ...


async def create_database(maintenance_conn: Any, *, database_name: str) -> None:
    ...


async def drop_database(maintenance_conn: Any, *, database_name: str) -> None:
    ...


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
