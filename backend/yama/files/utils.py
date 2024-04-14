from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from yama.files.models import FilePath, FileRead, FileShare, FileWrite


async def read_file(
    path: FilePath,
    /,
    *,
    max_ancestor_distance: int | None = 0,
    max_descendant_distance: int | None = 0,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    files_dir: Path,
) -> FileRead:
    ...


async def write_file(
    file_write: FileWrite,
    path: FilePath,
    /,
    *,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    files_dir: Path,
) -> FileRead:
    ...


async def share_file(
    file_share: FileShare,
    path: FilePath,
    /,
    *,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    files_dir: Path,
) -> FileRead:
    ...
