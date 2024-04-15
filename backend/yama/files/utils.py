from pathlib import Path, PurePosixPath
from typing import assert_never
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import aliased

from yama.files.models import (
    FileAncestorFileDescendantTable,
    FilePath,
    FileRead,
    FileShare,
    FileTable,
    FileWrite,
    ShareTable,
    ShareType,
    UserAncestorUserDescendantTable,
)


async def read_file(
    id_or_path: UUID | FilePath,
    /,
    *,
    depth: int | None = 0,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    files_dir: Path,
) -> FileRead:
    id_ = await _id_or_path_to_id(
        id_or_path,
        root_dir_id=root_dir_id,
        working_dir_id=working_dir_id,
        connection=connection,
    )

    await _check_share_for_file_and_user(
        allowed_share_types=[ShareType.READ, ShareType.WRITE, ShareType.SHARE],
        file_id=id_,
        user_id=user_id,
        connection=connection,
    )

    # # Faster depth == 0 solution
    # descendants_query = (
    #     select(
    #         FileTable.id.label("ancestor_id"),
    #         FileTable.id,
    #         literal(".").label("name"),
    #         FileTable.type,
    #     )
    #     .where(FileTable.id == id_)
    # )

    # General solution
    fafd1 = aliased(FileAncestorFileDescendantTable)
    fafd2 = aliased(FileAncestorFileDescendantTable)
    descendants_query = (
        select(
            fafd2.ancestor_id,
            fafd2.descendant_id.label("id"),
            fafd2.descendant_path.label("name"),
            FileTable.type,
        )
        .select_from(fafd1, fafd2)
        .join(FileTable, fafd2.descendant_id == FileTable.id)
        .where(fafd1.ancestor_id == id_)
        .where(fafd2.descendant_id == fafd1.descendant_id)
        .where((fafd1.descendant_depth == 0) | (fafd2.descendant_depth == 1))
    )
    if depth is not None:
        descendants_query = descendants_query.where(fafd1.descendant_depth <= depth)
    descendants = (await connection.execute(descendants_query)).mappings().all()

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


async def _check_share_for_file_and_user(
    *,
    allowed_share_types: list[ShareType],
    file_id: UUID,
    user_id: UUID,
    connection: AsyncConnection,
) -> None:
    ancestor_file_ids_cte = (
        select(FileAncestorFileDescendantTable.ancestor_id)
        .where(FileAncestorFileDescendantTable.descendant_id == file_id)
        .cte()
    )
    ancestor_user_ids_cte = (
        select(UserAncestorUserDescendantTable.ancestor_id)
        .where(UserAncestorUserDescendantTable.descendant_id == user_id)
        .cte()
    )
    share_id_query = (
        select(ShareTable.id)
        .select_from(ShareTable)
        .join(ancestor_file_ids_cte, ShareTable.file_id == ancestor_file_ids_cte.c.ancestor_id)
        .join(ancestor_user_ids_cte, ShareTable.to_user_id == ancestor_user_ids_cte.c.ancestor_id)
        .where(ShareTable.type.in_([st.value for st in allowed_share_types]))
        .limit(1)
        .add_cte(ancestor_file_ids_cte)
        .add_cte(ancestor_user_ids_cte)
    )  # fmt: skip
    share_id = (
        (await connection.execute(share_id_query)).scalars().one_or_none()
    )  # TODO: Log
    if share_id is None:
        raise NotImplementedError()


async def _id_or_path_to_id(
    id_or_path: UUID | FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
) -> UUID:
    match id_or_path:
        case UUID():
            id_ = id_or_path
        case PurePosixPath():  # HACK: Type alias 'FilePath' cannot be used with 'match'
            id_ = await _path_to_id(
                id_or_path,
                root_dir_id=root_dir_id,
                working_dir_id=working_dir_id,
                connection=connection,
            )
        case _:
            assert_never(id_or_path)

    return id_


async def _id_or_path_to_parent_id(
    id_or_path: UUID | FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
) -> UUID:
    match id_or_path:
        case UUID():
            parent_id = await _id_to_parent_id(id_or_path, connection=connection)
        case PurePosixPath():  # HACK: Type alias 'FilePath' cannot be used with 'match'
            parent_id = await _path_to_parent_id(
                id_or_path,
                root_dir_id=root_dir_id,
                working_dir_id=working_dir_id,
                connection=connection,
            )
        case _:
            assert_never(id_or_path)

    return parent_id


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

    try:
        id_ = await _ancestor_id_and_descendant_path_to_id(
            ancestor_id, descendant_path, connection=connection
        )
    except FilesFileNotFoundError as e:
        raise FilesFileNotFoundError(path) from e

    return id_


async def _id_to_parent_id(id_: UUID, /, *, connection: AsyncConnection) -> UUID:
    parent_id_query = (
        select(FileAncestorFileDescendantTable.ancestor_id)
        .where(FileAncestorFileDescendantTable.descendant_id == id_)
        .where(FileAncestorFileDescendantTable.descendant_depth == 1)
    )
    parent_id = (await connection.execute(parent_id_query)).scalars().one_or_none()
    if parent_id is None:
        raise NotImplementedError()

    return id_


async def _path_to_parent_id(
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

    match len(descendant_path.parts):
        case 0:
            parent_id = await _id_to_parent_id(ancestor_id, connection=connection)
        case 1:
            parent_id = ancestor_id
        case _:
            parent_ancestor_id = ancestor_id
            parent_descendant_path = descendant_path.parent
            parent_id = await _ancestor_id_and_descendant_path_to_id(
                parent_ancestor_id, parent_descendant_path, connection=connection
            )

    return parent_id


def _path_to_ancestor_id_and_descendant_path(
    path: FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
) -> tuple[UUID, FilePath]:
    if path.is_absolute():
        ancestor_id = root_dir_id
        descendant_path = path.relative_to("/")
    else:
        ancestor_id = working_dir_id
        descendant_path = path

    return ancestor_id, descendant_path


async def _ancestor_id_and_descendant_path_to_id(
    ancestor_id: UUID,
    descendant_path: FilePath,
    /,
    *,
    connection: AsyncConnection,
) -> UUID:
    id_query = (
        select(FileAncestorFileDescendantTable.descendant_id)
        .where(FileAncestorFileDescendantTable.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendantTable.descendant_path == str(descendant_path))
    )
    id_ = (await connection.execute(id_query)).scalars().one_or_none()
    if id_ is None:
        raise FilesFileNotFoundError(descendant_path)

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
