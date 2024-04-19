from pathlib import Path, PurePosixPath
from typing import assert_never
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.files.models import (
    DirectoryContentFileRead,
    DirectoryContentRead,
    DirectoryRead,
    FileAncestorFileDescendantDb,
    FileDb,
    FilePath,
    FileRead,
    FileShare,
    FileShareDb,
    FileShareType,
    FileType,
    FileWrite,
    RegularContentRead,
    RegularRead,
)
from yama.users.models import UserAncestorUserDescendantDb


async def read_file(
    id_or_path: UUID | FilePath,
    /,
    *,
    metadata: bool = True,
    content: bool = False,
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
        allowed_types=[
            FileShareType.READ,
            FileShareType.WRITE,
            FileShareType.SHARE,
        ],
        file_id=id_,
        user_id=user_id,
        connection=connection,
    )

    file_query = select(FileDb.id, FileDb.type).where(FileDb.id == id_)
    file_row = (await connection.execute(file_query)).mappings().one()
    file_db = FileDb(id=file_row["id"], type=file_row["type"])

    content_files_query = (
        select(
            FileAncestorFileDescendantDb.descendant_path.label("name"),
            FileDb.id,
            FileDb.type,
        )
        .select_from(FileAncestorFileDescendantDb)
        .where((FileAncestorFileDescendantDb.ancestor_id == id_) & (FileAncestorFileDescendantDb.descendant_depth == 1))
        .join(FileDb, FileAncestorFileDescendantDb.descendant_id == FileDb.id)
    )  # fmt: skip
    content_files_rows = (
        (await connection.execute(content_files_query)).mappings().all()
    )
    content_files_db = [
        (row["name"], FileDb(id=row["id"], type=row["type"]))
        for row in content_files_rows
    ]

    content_files = []
    for name, content_file_db in content_files_db:
        content_file_file: FileRead
        content_file_file_type = FileType(content_file_db.type)
        match content_file_file_type:
            case FileType.REGULAR:
                content_file_file = RegularRead(
                    id=content_file_db.id, type=content_file_file_type
                )
            case FileType.DIRECTORY:
                content_file_file = DirectoryRead(
                    id=content_file_db.id, type=content_file_file_type
                )
            case _:
                assert_never(content_file_file_type)
        content_file = DirectoryContentFileRead(name=name, file=content_file_file)
        content_files.append(content_file)

    file: FileRead
    file_type = FileType(file_db.type)
    match file_type:
        case FileType.REGULAR:
            file = RegularRead(
                id=file_db.id,
                type=file_type,
                content=RegularContentRead(
                    physical_path=_id_to_physical_path(file_db.id, files_dir=files_dir)
                ),
            )
        case FileType.DIRECTORY:
            file = DirectoryRead(
                id=file_db.id,
                type=file_type,
                content=DirectoryContentRead(
                    count_=len(content_files), items=content_files
                ),
            )
        case _:
            assert_never(file_type)

    return file


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


def _make_regular_content(*, id_: UUID, files_dir: Path) -> RegularContentRead:
    physical_path = _id_to_physical_path(id_, files_dir=files_dir)
    return RegularContentRead(physical_path=physical_path)


async def _make_directory_content(
    *, id_: UUID, connection: AsyncConnection
) -> DirectoryContentRead:
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
        file: FileRead
        match type_ := FileType(file_db.type):
            case FileType.REGULAR:
                file = RegularRead(id=file_db.id, type=type_)
            case FileType.DIRECTORY:
                file = DirectoryRead(id=file_db.id, type=type_)
            case _:
                assert_never(type_)

        content_file = DirectoryContentFileRead(name=name, file=file)
        content_files.append(content_file)

    return DirectoryContentRead(count_=len(content_files), items=content_files)


def _id_to_physical_path(id: UUID, /, *, files_dir: Path) -> Path:
    return files_dir / id.hex


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
        select(FileAncestorFileDescendantDb.descendant_id)
        .where(FileAncestorFileDescendantDb.ancestor_id == ancestor_id)
        .where(FileAncestorFileDescendantDb.descendant_path == str(descendant_path))
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
