from collections.abc import Sequence
from pathlib import Path
from typing import assert_never
from uuid import UUID

import aiofiles
from fastapi import UploadFile
from sqlalchemy import case, delete, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.files.models import (
    DirectoryCreateTuple,
    DirectoryEntryReadTuple,
    DirectoryReadTuple,
    File,
    FileAncestorFileDescendant,
    FileCreateTuple,
    FileName,
    FileNameAdapter,
    FilePath,
    FilePathAdapter,
    FileReadTuple,
    FileTypeEnum,
    RegularFileCreateTuple,
    RegularFileReadTuple,
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
async def create_file(
    path: FilePath,
    /,
    *,
    file_in: FileCreateTuple,
    user_id: UUID,
    working_dir_id: UUID,
    files_dir: Path,
    root_dir_id: UUID,
    upload_chunk_size: int,
    upload_max_file_size: int,
    connection: AsyncConnection,
) -> UUID:
    if not await file_exists(
        path.parent,
        type_=FileTypeEnum.DIRECTORY,
        user_id=user_id,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    ):
        raise FilesFileNotFoundError(path.parent)
    if await file_exists(
        path,
        user_id=user_id,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    ):
        raise FilesFileExistsError(path)

    insert_file_query = insert(File).values(type=file_in.type).returning(File)
    file_row = (await connection.execute(insert_file_query)).mappings().one()
    file = File(**file_row)

    (
        parent_ancestor_id,
        parent_descendant_path,
    ) = _path_to_ancestor_id_and_descendant_path(
        path.parent, working_dir_id=working_dir_id, root_dir_id=root_dir_id
    )
    parent_id_query = (
        select(FileAncestorFileDescendant.descendant_id)
        .where(FileAncestorFileDescendant.ancestor_id == parent_ancestor_id)
        .where(FileAncestorFileDescendant.descendant_path == parent_descendant_path)
    )
    parent_id = (await connection.execute(parent_id_query)).scalar_one()

    insert_dot_query = insert(FileAncestorFileDescendant).values(
        ancestor_id=file.id,
        descendant_id=file.id,
        descendant_path=".",
        descendant_depth=0,
    )
    await connection.execute(insert_dot_query)

    insert_ancestors_query = insert(FileAncestorFileDescendant).from_select(
        ["ancestor_id", "descendant_id", "descendant_path", "descendant_depth"],
        select(
            FileAncestorFileDescendant.ancestor_id,
            literal(file.id).label("descendant_id"),
            case(
                (FileAncestorFileDescendant.descendant_path == ".", literal(path.name)),
                else_=(
                    FileAncestorFileDescendant.descendant_path
                    + "/"
                    + literal(path.name)
                ),
            ).label("descendant_path"),
            (FileAncestorFileDescendant.descendant_depth + 1).label("descendant_depth"),
        ).where(FileAncestorFileDescendant.descendant_id == parent_id),
    )
    await connection.execute(insert_ancestors_query)

    match file_in:
        case RegularFileCreateTuple(content=content):
            await _write_file(
                content,
                _id_to_physical_path(file.id, files_dir=files_dir),
                chunk_size=upload_chunk_size,
                max_file_size=upload_max_file_size,
            )
        case DirectoryCreateTuple():
            ...
        case _:
            assert_never(file_in)

    await connection.commit()

    return file.id


# FIXME: Add security
async def get_file(
    path: FilePath,
    /,
    *,
    type_: FileTypeEnum | None = None,
    user_id: UUID,
    working_dir_id: UUID,
    files_dir: Path,
    root_dir_id: UUID,
    connection: AsyncConnection,
) -> FileReadTuple:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, working_dir_id=working_dir_id, root_dir_id=root_dir_id
    )
    file_query = (
        select(File)
        .select_from(FileAncestorFileDescendant)
        .join(File, FileAncestorFileDescendant.descendant_id == File.id)
        .where(FileAncestorFileDescendant.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendant.descendant_path == descendant_path)
    )
    file_row = (await connection.execute(file_query)).mappings().one_or_none()
    if file_row is None:
        raise FilesFileNotFoundError(path)
    file = File(**file_row)

    match type_:
        case None:
            ...
        case FileTypeEnum.DIRECTORY:
            if file.type != FileTypeEnum.DIRECTORY:
                raise FilesNotADirectoryError(path)
        case FileTypeEnum.REGULAR:
            if file.type != FileTypeEnum.REGULAR:
                raise FilesIsADirectoryError(path)
        case _:
            assert_never(type_)

    match file.type:
        case FileTypeEnum.DIRECTORY:
            directory_entries_query = (
                select(File.id, File.type, FileAncestorFileDescendant.descendant_path)
                .select_from(FileAncestorFileDescendant)
                .join(File, FileAncestorFileDescendant.descendant_id == File.id)
                .where(FileAncestorFileDescendant.ancestor_id == file.id)
                .where(FileAncestorFileDescendant.descendant_depth == 1)
            )
            directory_entries_rows = (
                (await connection.execute(directory_entries_query)).mappings().all()
            )
            directory_entries = [
                DirectoryEntryReadTuple(
                    id=row["id"], type=row["type"], name=row["descendant_path"]
                )
                for row in directory_entries_rows
            ]
            return DirectoryReadTuple(
                id=file.id, type=file.type, content=directory_entries
            )
        case FileTypeEnum.REGULAR:
            return RegularFileReadTuple(
                id=file.id,
                type=file.type,
                content_physical_path=_id_to_physical_path(
                    file.id, files_dir=files_dir
                ),
            )
        case _:
            assert_never(file.type)


# FIXME: Add security
async def delete_file(
    path: FilePath,
    /,
    *,
    type_: FileTypeEnum | None = None,
    user_id: UUID,
    working_dir_id: UUID,
    files_dir: Path,
    root_dir_id: UUID,
    connection: AsyncConnection,
) -> UUID:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, working_dir_id=working_dir_id, root_dir_id=root_dir_id
    )

    file_query = (
        select(File)
        .select_from(FileAncestorFileDescendant)
        .join(File, FileAncestorFileDescendant.descendant_id == File.id)
        .where(FileAncestorFileDescendant.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendant.descendant_path == descendant_path)
    )
    file = (await connection.execute(file_query)).scalar_one_or_none()
    if file is None:
        raise FilesFileNotFoundError(path)

    match type_:
        case None:
            ...
        case FileTypeEnum.DIRECTORY:
            if file.type != FileTypeEnum.DIRECTORY:
                raise FilesNotADirectoryError(path)
        case FileTypeEnum.REGULAR:
            if file.type != FileTypeEnum.REGULAR:
                raise FilesIsADirectoryError(path)
        case _:
            assert_never(type_)

    delete_descendants_cte = (  # Includes the file itself
        delete(FileAncestorFileDescendant)
        .where(FileAncestorFileDescendant.ancestor_id == file.id)
        .returning(FileAncestorFileDescendant.descendant_id)
        .cte()
    )
    delete_descendant_files_cte = (
        delete(File)
        .where(File.id == delete_descendants_cte.c.descendant_id)
        .returning(File.id, File.type)
        .cte()
    )
    select_regular_descendant_ids_query = select(
        delete_descendant_files_cte.c.id
    ).where(delete_descendant_files_cte.c.type == FileTypeEnum.REGULAR)
    regular_descendant_ids: Sequence[UUID] = (  # HACK: Implicit type cast
        (await connection.execute(select_regular_descendant_ids_query)).scalars().all()
    )

    await connection.commit()

    for regular_descendant_id in regular_descendant_ids:
        physical_path = _id_to_physical_path(regular_descendant_id, files_dir=files_dir)
        physical_path.unlink(missing_ok=True)  # TODO: Log

    return file.id


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
    type_: FileTypeEnum | None = None,
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
    if type_ is not None:
        file_exists_subquery_base = file_exists_subquery_base.join(
            File, FileAncestorFileDescendant.descendant_id == File.id
        ).where(File.type == type_)
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


def _path_to_file_name(path: str) -> FileName:
    file_path = FilePathAdapter.validate_python(path)
    file_name = FileNameAdapter.validate_python(file_path.name)
    return file_name
