from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.files.models import (
    FileAncestorFileDescendantTable,
    FilePath,
    FileRead,
    FileShare,
    FileTable,
    FileWrite,
)


async def read_file(
    id_or_path: UUID | FilePath,
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
    id_or_path: UUID | FilePath,
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
    id_or_path: UUID | FilePath,
    /,
    *,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    files_dir: Path,
) -> FileRead:
    ...


def _path_to_ancestor_id_and_descendant_path(
    path: FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
) -> tuple[UUID, str]:
    if path.is_absolute():
        ancestor_id = root_dir_id
        descendant_path = str(path.relative_to("/"))
    else:
        ancestor_id = working_dir_id
        descendant_path = str(path)

    return ancestor_id, descendant_path


async def _path_to_id(
    path: FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
) -> UUID:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, root_dir_id=root_dir_id, working_dir_id=working_dir_id
    )

    file_query = (
        select(FileTable.id)
        .select_from(FileAncestorFileDescendantTable)
        .join(FileTable, FileAncestorFileDescendantTable.descendant_id == FileTable.id)
        .where(FileAncestorFileDescendantTable.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendantTable.descendant_path == descendant_path)
    )
    id_ = (await connection.execute(file_query)).scalars().one_or_none()
    if id_ is None:
        raise FilesFileNotFoundError(path)

    return id_


class UploadFileTooLargeError(Exception):
    ...


class FilesFileError(Exception):
    def __init__(self, path: FilePath) -> None:
        self.path = path

    def __str__(self) -> str:
        return f"'{self.path}'"


class FilesFileExistsError(FilesFileError):
    ...


class FilesFileNotFoundError(FilesFileError):
    ...


class FilesIsADirectoryError(FilesFileError):
    ...


class FilesNotADirectoryError(FilesFileError):
    ...


# class FilesPermissionError(FilesFileError):
#     ...
