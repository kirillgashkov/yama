from collections import OrderedDict, defaultdict
from pathlib import Path, PurePosixPath
from typing import NamedTuple, assert_never
from uuid import UUID

from sqlalchemy import and_, case, delete, insert, literal, select, union
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.file.driver.utils import Driver
from yama.file.models import (
    Directory,
    DirectoryContent,
    DirectoryContentFile,
    File,
    FileAncestorFileDescendantDb,
    FileDb,
    FileName,
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

    if id_ is not None and not overwrite:
        raise FilesFileExistsError(id_)

    raise NotImplementedError()


async def _add_file(
    file_write: FileWrite,
    parent_id: UUID,
    name: FileName,
    /,
    *,
    user_id: UUID,
    connection: AsyncConnection,
) -> File:
    insert_file_db_query = (
        insert(FileDb).values(type=file_write.type.value).returning(FileDb)
    )
    file_db_row = (await connection.execute(insert_file_db_query)).mappings().one()
    file_db = FileDb(**file_db_row)

    insert_share_db_query = insert(FileShareDb).values(
        type=FileShareType.SHARE.value,
        file_id=file_db.id,
        user_id=user_id,
        created_by=user_id,
    )
    await connection.execute(insert_share_db_query)

    insert_ancestors_db_query = insert(FileAncestorFileDescendantDb).from_select(
        ["ancestor_id", "descendant_id", "descendant_path", "descendant_depth"],
        union(
            select(
                literal(file_db.id).label("ancestor_id"),
                literal(file_db.id).label("descendant_id"),
                literal(".").label("descendant_path"),
                literal(0).label("descendant_depth"),
            ),
            select(
                FileAncestorFileDescendantDb.ancestor_id,
                literal(file_db.id).label("descendant_id"),
                case(
                    (FileAncestorFileDescendantDb.descendant_path == ".", literal(name)),
                    else_=(FileAncestorFileDescendantDb.descendant_path + "/" + literal(name)),
                ).label("descendant_path"),
                (FileAncestorFileDescendantDb.descendant_depth + 1).label("descendant_depth"),
            ).where(FileAncestorFileDescendantDb.descendant_id == parent_id),
        ),
    )  # fmt: skip
    await connection.execute(insert_ancestors_db_query)

    # await connection.commit()  # Maybe yield before committing?

    raise NotImplementedError()


# TODO: Make id_ parameter positional
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


async def _move_file(
    id_: UUID,
    new_parent_id: UUID,
    new_name: FileName,
    /,
    *,
    connection: AsyncConnection,
) -> File:
    select_descendants_db_cte = (
        select(
            FileAncestorFileDescendantDb.descendant_id,
            FileAncestorFileDescendantDb.descendant_path,
            FileAncestorFileDescendantDb.descendant_depth,
        )
        .where(FileAncestorFileDescendantDb.ancestor_id == id_)
        .cte()
    )
    delete_old_descendant_ancestors_cte = (
        delete(FileAncestorFileDescendantDb)
        .where(FileAncestorFileDescendantDb.descendant_id == select_descendants_db_cte.c.descendant_id)
        .where(FileAncestorFileDescendantDb.descendant_depth > select_descendants_db_cte.c.descendant_depth)
        .cte()
    )  # fmt: skip
    insert_new_descendant_ancestors_query = (
        insert(FileAncestorFileDescendantDb)
        .from_select(
            ["ancestor_id", "descendant_id", "descendant_path", "descendant_depth"],
            select(
                FileAncestorFileDescendantDb.ancestor_id,
                select_descendants_db_cte.c.descendant_id,
                case(
                    (and_(FileAncestorFileDescendantDb.descendant_path == ".", select_descendants_db_cte.c.descendant_path == "."), literal(new_name)),
                    (and_(FileAncestorFileDescendantDb.descendant_path == ".", select_descendants_db_cte.c.descendant_path != "."), literal(new_name) + "/" + select_descendants_db_cte.c.descendant_path),
                    (and_(FileAncestorFileDescendantDb.descendant_path != ".", select_descendants_db_cte.c.descendant_path == "."), FileAncestorFileDescendantDb.descendant_path + "/" + literal(new_name)),
                    else_=(FileAncestorFileDescendantDb.descendant_path + "/" + literal(new_name) + "/" + select_descendants_db_cte.c.descendant_path),
                ).label("descendant_path"),
                (FileAncestorFileDescendantDb.descendant_depth + select_descendants_db_cte.c.descendant_depth + 1).label("descendant_depth"),
            )
            .select_from(FileAncestorFileDescendantDb, select_descendants_db_cte)
            .where(FileAncestorFileDescendantDb.descendant_id == new_parent_id)
        )
        .add_cte(select_descendants_db_cte)
        .add_cte(delete_old_descendant_ancestors_cte)
    )  # fmt: skip
    await connection.execute(insert_new_descendant_ancestors_query)

    # await connection.commit()

    raise NotImplementedError()


async def _remove_file(id_: UUID, /, *, connection: AsyncConnection) -> File:
    delete_descendants_db_cte = (
        delete(FileAncestorFileDescendantDb)
        .where(FileAncestorFileDescendantDb.ancestor_id == id_)
        .returning(FileAncestorFileDescendantDb.descendant_id)
        .cte()
    )
    delete_descendant_ancestors_db_cte = (
        delete(FileAncestorFileDescendantDb)
        .where(FileAncestorFileDescendantDb.descendant_id == delete_descendants_db_cte.c.descendant_id)
        .cte()
    )  # fmt: skip
    delete_descendant_shares_db_cte = (
        delete(FileShareDb)
        .where(FileShareDb.file_id == delete_descendants_db_cte.c.descendant_id)
        .cte()
    )
    delete_descendant_files_db_query = (
        delete(FileDb)
        .where(FileDb.id == delete_descendants_db_cte.c.descendant_id)
        .returning(FileDb)
        .add_cte(delete_descendants_db_cte)
        .add_cte(delete_descendant_ancestors_db_cte)
        .add_cte(delete_descendant_shares_db_cte)
    )
    descendant_files_db_rows = (
        (await connection.execute(delete_descendant_files_db_query)).mappings().all()
    )
    _ = descendant_files_db_rows

    # await connection.commit()

    raise NotImplementedError()


class _FileParentIdAndName(NamedTuple):
    parent_id: UUID
    name: FileName


def _make_files(
    files_db_with_parent_id_and_name: list[tuple[FileDb, _FileParentIdAndName | None]],
) -> list[File]:
    id_to_file_db: OrderedDict[UUID, FileDb] = OrderedDict()
    parent_id_to_children: defaultdict[UUID, list[tuple[FileName, UUID]]] = defaultdict(
        list
    )
    child_ids: set[UUID] = set()

    for file_db, parent_id_and_name in files_db_with_parent_id_and_name:
        id_to_file_db[file_db.id] = file_db

        if parent_id_and_name:
            parent_id, name = parent_id_and_name
            parent_id_to_children[parent_id].append((name, file_db.id))
            child_ids.add(file_db.id)

    # root_ids doesn't include parent IDs without FileDb.  # FIXME: Include or raise an error.
    root_ids: list[UUID] = []

    for id_ in id_to_file_db:
        if id_ not in child_ids:
            root_ids.append(id_)

    id_to_file: dict[UUID, File] = {}
    stack: list[UUID] = root_ids

    while stack and (id_ := stack.pop()):
        children = parent_id_to_children[id_]

        not_made_child_ids: list[UUID] = []
        for _, child_id in children:
            if child_id not in id_to_file:
                not_made_child_ids.append(child_id)

        if not_made_child_ids:
            stack.append(id_)
            stack.extend(not_made_child_ids)
            continue

        content_files: list[DirectoryContentFile] = []
        for child_name, child_id in children:
            child_file = id_to_file[child_id]
            content_file = DirectoryContentFile(name=child_name, file=child_file)
            content_files.append(content_file)

        file: File
        file_db = id_to_file_db[id_]
        file_type = FileType(file_db.type)
        match file_type:
            case FileType.REGULAR:
                if content_files:
                    raise ValueError("Regular file can't have content files")
                file = Regular(id=file_db.id, type=file_type)  # FIXME: content?
            case FileType.DIRECTORY:
                file_content = DirectoryContent(
                    count_=len(content_files), items=content_files
                )
                file = Directory(id=file_db.id, type=file_type, content=file_content)
            case _:
                assert_never(file_type)

        id_to_file[id_] = file

    files: list[File] = []
    for root_id in root_ids:
        file = id_to_file[root_id]
        files.append(file)

    return files


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
        raise FilesPermissionError(file_id)


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
        raise FilesFileNotFoundError(ancestor_id, descendant_path)

    return id_


async def _id_to_parent_id(id_: UUID, /, *, connection: AsyncConnection) -> UUID:
    parent_id_query = (
        select(FileAncestorFileDescendantDb.ancestor_id)
        .where(FileAncestorFileDescendantDb.descendant_id == id_)
        .where(FileAncestorFileDescendantDb.descendant_depth == 1)
    )
    parent_id = (await connection.execute(parent_id_query)).scalars().one_or_none()
    if parent_id is None:
        # Ideally descendant_path should be '..' but since FilePath
        # doesn't support it, '.' (the default) will do.
        raise FilesFileNotFoundError(id_)

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
                raise FilesFileNotFoundError(parent_ancestor_id, parent_descendant_path)
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
                raise FilesFileNotFoundError(ancestor_id, parent_descendant_path)
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


class FilesFileError(Exception):
    def __init__(
        self, ancestor_id: UUID, descendant_path: FilePath = PurePosixPath("."), /
    ) -> None:
        self.ancestor_id = ancestor_id
        self.descendant_path = descendant_path

    def __str__(self) -> str:
        return f"'{self.descendant_path}' relative to {self.ancestor_id}"


class FilesFileExistsError(FilesFileError):
    ...


class FilesFileNotFoundError(FilesFileError):
    ...


class FilesIsADirectoryError(FilesFileError):
    ...


class FilesNotADirectoryError(FilesFileError):
    ...


class FilesPermissionError(FilesFileError):
    ...
