from pathlib import Path, PurePosixPath
from typing import assert_never
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.file.driver.utils import Driver
from yama.file.models import (
    Directory,
    DirectoryContent,
    DirectoryContentFile,
    File,
    FileAncestorFileDescendantDb,
    FileDb,
    FilePath,
    FileShareDb,
    FileShareType,
    FileType,
    FileWrite,
    Regular,
    RegularContent,
)
from yama.user.models import UserAncestorUserDescendantDb


async def read_file(
    id_or_path: UUID | FilePath,
    /,
    *,
    content: bool = False,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    files_dir: Path,
) -> File:
    id_ = await _id_or_path_to_id(
        id_or_path,
        root_dir_id=root_dir_id,
        working_dir_id=working_dir_id,
        connection=connection,
    )

    await _check_share_for_file_and_user(
        allowed_types=[
            FileShareType.READ,
            FileShareType.WRITE,
            FileShareType.SHARE,
        ],
        file_id=id_,
        user_id=user_id,
        connection=connection,
    )

    file = await _get_file(
        id_=id_, content=content, connection=connection, files_dir=files_dir
    )

    return file


async def write_file(
    file_write: FileWrite,
    id_or_path: UUID | FilePath,
    /,
    *,
    overwrite: bool = False,
    root_dir_id: UUID,
    user_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
    driver: Driver,
) -> File:
    parent_id, id_ = await _id_or_path_to_parent_id_and_id_or_none(
        id_or_path,
        root_dir_id=root_dir_id,
        working_dir_id=working_dir_id,
        connection=connection,
    )

    await _check_share_for_file_and_user(
        allowed_types=[
            FileShareType.WRITE,
            FileShareType.SHARE,
        ],
        file_id=id_ or parent_id,
        user_id=user_id,
        connection=connection,
    )

    raise NotImplementedError()


async def _get_file(
    *, id_: UUID, content: bool, files_dir: Path, connection: AsyncConnection
) -> File:
    file_db_query = select(FileDb).where(FileDb.id == id_)
    file_db_row = (await connection.execute(file_db_query)).mappings().one()
    file_db = FileDb(**file_db_row)

    file: File
    match type_ := FileType(file_db.type):
        case FileType.REGULAR:
            if content:
                file = Regular(
                    id=file_db.id,
                    type=type_,
                    content=_get_regular_content(id_=file_db.id, files_dir=files_dir),
                )
            else:
                file = Regular(id=file_db.id, type=type_)
        case FileType.DIRECTORY:
            if content:
                file = Directory(
                    id=file_db.id,
                    type=type_,
                    content=(
                        await _get_directory_content(
                            id_=file_db.id, connection=connection
                        )
                    ),
                )
            else:
                file = Directory(id=file_db.id, type=type_)

        case _:
            assert_never(type_)

    return file


def _get_regular_content(*, id_: UUID, files_dir: Path) -> RegularContent:
    ...


async def _get_directory_content(
    *, id_: UUID, connection: AsyncConnection
) -> DirectoryContent:
    content_files_db_query = (
        select(
            FileAncestorFileDescendantDb.descendant_path.label("name"),
            FileDb.id,
            FileDb.type,
        )
        .select_from(FileAncestorFileDescendantDb)
        .where(FileAncestorFileDescendantDb.ancestor_id == id_)
        .where(FileAncestorFileDescendantDb.descendant_depth == 1)
        .join(FileDb, FileAncestorFileDescendantDb.descendant_id == FileDb.id)
    )
    content_files_db_rows = (
        (await connection.execute(content_files_db_query)).mappings().all()
    )
    content_files_db: list[tuple[str, FileDb]] = [
        (row["name"], FileDb(id=row["id"], type=row["type"]))
        for row in content_files_db_rows
    ]  # HACK: Implicit type cast

    content_files = []
    for name, file_db in content_files_db:
        file: File
        match type_ := FileType(file_db.type):
            case FileType.REGULAR:
                file = Regular(id=file_db.id, type=type_)
            case FileType.DIRECTORY:
                file = Directory(id=file_db.id, type=type_)
            case _:
                assert_never(type_)

        content_file = DirectoryContentFile(name=name, file=file)
        content_files.append(content_file)

    return DirectoryContent(count_=len(content_files), items=content_files)


async def _check_share_for_file_and_user(
    *,
    allowed_types: list[FileShareType],
    file_id: UUID,
    user_id: UUID,
    connection: AsyncConnection,
) -> None:
    ancestor_file_ids_cte = (
        select(FileAncestorFileDescendantDb.ancestor_id)
        .where(FileAncestorFileDescendantDb.descendant_id == file_id)
        .cte()
    )
    ancestor_user_ids_cte = (
        select(UserAncestorUserDescendantDb.ancestor_id)
        .where(UserAncestorUserDescendantDb.descendant_id == user_id)
        .cte()
    )
    share_id_query = (
        select(FileShareDb.id)
        .select_from(FileShareDb)
        .join(ancestor_file_ids_cte, FileShareDb.file_id == ancestor_file_ids_cte.c.ancestor_id)
        .join(ancestor_user_ids_cte, FileShareDb.user_id == ancestor_user_ids_cte.c.ancestor_id)
        .where(FileShareDb.type.in_([t.value for t in allowed_types]))
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


async def _id_or_path_to_parent_id_and_id_or_none(
    id_or_path: UUID | FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
) -> tuple[UUID, UUID | None]:
    parent_id: UUID
    id_: UUID | None
    match id_or_path:
        case UUID():
            parent_id = await _id_to_parent_id(id_or_path, connection=connection)
            id_ = id_or_path
        case PurePosixPath():  # HACK: Type alias 'FilePath' cannot be used with 'match'
            parent_id, id_ = await _path_to_parent_id_and_id_or_none(
                id_or_path,
                root_dir_id=root_dir_id,
                working_dir_id=working_dir_id,
                connection=connection,
            )
        case _:
            assert_never(id_or_path)

    return parent_id, id_


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

    id_ = await _ancestor_id_and_descendant_path_to_id_or_none(
        ancestor_id, descendant_path, connection=connection
    )
    if id_ is None:
        raise FilesFileNotFoundError(path)

    return id_


async def _id_to_parent_id(id_: UUID, /, *, connection: AsyncConnection) -> UUID:
    parent_id_query = (
        select(FileAncestorFileDescendantDb.ancestor_id)
        .where(FileAncestorFileDescendantDb.descendant_id == id_)
        .where(FileAncestorFileDescendantDb.descendant_depth == 1)
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
            parent_id_or_none = await _ancestor_id_and_descendant_path_to_id_or_none(
                parent_ancestor_id, parent_descendant_path, connection=connection
            )
            if parent_id_or_none is None:
                raise FilesFileNotFoundError(parent_descendant_path)
            parent_id = parent_id_or_none

    return parent_id


async def _path_to_parent_id_and_id_or_none(
    path: FilePath,
    /,
    *,
    root_dir_id: UUID,
    working_dir_id: UUID,
    connection: AsyncConnection,
) -> tuple[UUID, UUID | None]:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, root_dir_id=root_dir_id, working_dir_id=working_dir_id
    )

    parent_id: UUID
    id_: UUID | None
    match len(descendant_path.parts):
        case 0:
            parent_id = await _id_to_parent_id(ancestor_id, connection=connection)
            id_ = ancestor_id
        case 1:
            parent_id = ancestor_id
            id_ = await _ancestor_id_and_descendant_path_to_id_or_none(
                ancestor_id, descendant_path, connection=connection
            )
        case _:
            parent_descendant_path = descendant_path.parent

            descendant_path_to_id = await _ancestor_id_and_descendant_paths_to_ids(
                ancestor_id,
                [parent_descendant_path, descendant_path],
                connection=connection,
            )

            parent_id_or_none = descendant_path_to_id.get(parent_descendant_path)
            if parent_id_or_none is None:
                raise FilesFileNotFoundError(parent_descendant_path)
            parent_id = parent_id_or_none
            id_ = descendant_path_to_id.get(descendant_path)

    return parent_id, id_


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


async def _ancestor_id_and_descendant_path_to_id_or_none(
    ancestor_id: UUID,
    descendant_path: FilePath,
    /,
    *,
    connection: AsyncConnection,
) -> UUID | None:
    descendant_path_to_id = await _ancestor_id_and_descendant_paths_to_ids(
        ancestor_id, [descendant_path], connection=connection
    )
    return descendant_path_to_id.get(descendant_path)


async def _ancestor_id_and_descendant_paths_to_ids(
    ancestor_id: UUID,
    descendant_paths: list[FilePath],
    /,
    *,
    connection: AsyncConnection,
) -> dict[FilePath, UUID]:
    descendant_path_to_id_query = (
        select(
            FileAncestorFileDescendantDb.descendant_path,
            FileAncestorFileDescendantDb.descendant_id,
        )
        .where(FileAncestorFileDescendantDb.ancestor_id == ancestor_id)
        .where(
            FileAncestorFileDescendantDb.descendant_path.in_(
                str(p) for p in descendant_paths
            )
        )
    )
    descendant_path_to_id_rows = (
        (await connection.execute(descendant_path_to_id_query)).mappings().all()
    )
    descendant_path_to_id: dict[FilePath, UUID] = {
        PurePosixPath(row["descendant_path"]): row["descendant_id"]
        for row in descendant_path_to_id_rows
    }  # HACK: Implicit type cast

    return descendant_path_to_id


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
