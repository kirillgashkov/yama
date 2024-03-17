from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.files.models import (
    File,
    FileAncestorFileDescendant,
    FileName,
    FilePath,
    FileTypeEnum,
)


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


# FIXME: Add security
# FIXME: Ensure atomicity
# TODO: Refactor `type` and `content` into "directory" and "regular, content" variants
# TODO: Refactor queries into one query
async def create_file(
    parent_path: FilePath,
    name: FileName,
    /,
    *,
    type: FileTypeEnum,
    content: UploadFile | None = None,
    user_id: UUID,
    working_dir_id: UUID,
    files_dir: Path,
    root_dir_id: UUID,
    upload_chunk_size: int,
    upload_max_file_size: int,
    connection: AsyncConnection,
) -> UUID:
    path = parent_path / name

    if not await file_exists(
        parent_path,
        type=FileTypeEnum.DIRECTORY,
        user_id=user_id,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    ):
        raise FilesFileNotFoundError(parent_path)
    if await file_exists(
        path,
        user_id=user_id,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    ):
        raise FilesFileExistsError(path)

    insert_file_query = insert(File).values(type=type).returning(File.id)
    id = (await connection.execute(insert_file_query)).scalar_one()

    ancestor_id, parent_descendant_path = _path_to_ancestor_id_and_descendant_path(
        parent_path, working_dir_id=working_dir_id, root_dir_id=root_dir_id
    )
    parent_id_query = (
        select(FileAncestorFileDescendant.descendant_id)
        .where(FileAncestorFileDescendant.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendant.descendant_path == parent_descendant_path)
    )
    parent_id = (await connection.execute(parent_id_query)).scalar_one()

    parent_ancestors_query = select(FileAncestorFileDescendant).where(
        FileAncestorFileDescendant.descendant_id == parent_id
    )
    parent_ancestors = (
        (await connection.execute(parent_ancestors_query)).scalars().all()
    )

    insert_dot_query = insert(FileAncestorFileDescendant).values(
        ancestor_id=id, descendant_id=id, descendant_path=".", depth=0
    )
    await connection.execute(insert_dot_query)

    for parent_ancestor in parent_ancestors:  # Includes the parent itself
        insert_ancestor_query = insert(FileAncestorFileDescendant).values(
            ancestor_id=parent_ancestor.ancestor_id,
            descendant_id=id,
            descendant_path=(
                name
                if parent_ancestor.descendant_path == "."
                else parent_ancestor.descendant_path + "/" + name
            ),
            depth=parent_ancestor.depth + 1,
        )
        await connection.execute(insert_ancestor_query)

    if type == FileTypeEnum.REGULAR:
        if content is None:
            raise ValueError("Content must be provided for regular files")

        await _write_file(
            content,
            _id_to_physical_path(id, files_dir=files_dir),
            chunk_size=upload_chunk_size,
            max_file_size=upload_max_file_size,
        )

    await connection.commit()

    return id


def _path_to_ancestor_id_and_descendant_path(
    path: FilePath,
    /,
    *,
    working_dir_id: UUID,
    root_dir_id: UUID,
) -> tuple[UUID, str]:
    if path.is_absolute():
        ancestor_id = root_dir_id
        descendant_path = str(path.relative_to("/"))
    else:
        ancestor_id = working_dir_id
        descendant_path = str(path)

    return ancestor_id, descendant_path


# FIXME: Add security
async def file_exists(
    path: FilePath,
    /,
    *,
    type: FileTypeEnum | None = None,
    user_id: UUID,
    working_dir_id: UUID,
    root_dir_id: UUID,
    connection: AsyncConnection,
) -> bool:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, root_dir_id=root_dir_id, working_dir_id=working_dir_id
    )

    file_exists_subquery_base = (
        select(1)
        .select_from(FileAncestorFileDescendant)
        .where(FileAncestorFileDescendant.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendant.descendant_path == descendant_path)
    )
    if type is not None:
        file_exists_subquery_base = file_exists_subquery_base.join(
            File, FileAncestorFileDescendant.descendant_id == File.id
        ).where(File.type == type)
    file_exists_subquery = file_exists_subquery_base.exists()

    query = select(file_exists_subquery)
    return (await connection.execute(query)).scalar_one()


async def _write_file(
    upload_file: UploadFile,
    physical_path: Path,
    /,
    *,
    chunk_size: int,
    max_file_size: int,
) -> int:
    file_size = 0

    async with aiofiles.open(physical_path, "wb") as file_out:
        while chunk := await upload_file.read(chunk_size):
            file_size += len(chunk)

            if file_size > max_file_size:
                raise UploadFileTooLargeError()

            await file_out.write(chunk)

    return file_size


def _id_to_physical_path(id: UUID, /, *, files_dir: Path) -> Path:
    return files_dir / id.hex
