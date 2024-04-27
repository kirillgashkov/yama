from collections import OrderedDict, defaultdict
from collections.abc import Iterable
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import AsyncIterator, NamedTuple, assert_never
from uuid import UUID

from sqlalchemy import and_, case, delete, insert, literal, select, union
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import aliased

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


@asynccontextmanager
async def _add_file(
    file_write: FileWrite,
    parent_id: UUID,
    name: FileName,
    /,
    *,
    user_id: UUID,
    connection: AsyncConnection,
) -> AsyncIterator[File]:
    insert_file_db_cte = (
        insert(FileDb).values(type=file_write.type.value).returning(FileDb).cte()
    )
    insert_share_db_cte = (
        insert(FileShareDb)
        .from_select(
            ["type", "file_id", "user_id", "created_by"],
            select(
                literal(FileShareType.SHARE.value).label("type"),
                insert_file_db_cte.c.id,
                literal(user_id).label("user_id"),
                literal(user_id).label("created_by"),
            ),
        )
        .cte()
    )
    insert_ancestors_db_cte = (
        insert(FileAncestorFileDescendantDb)
        .from_select(
            ["ancestor_id", "descendant_id", "descendant_path", "descendant_depth"],
            union(
                select(
                    insert_file_db_cte.c.id.label("ancestor_id"),
                    insert_file_db_cte.c.id.label("descendant_id"),
                    literal(".").label("descendant_path"),
                    literal(0).label("descendant_depth"),
                ),
                select(
                    FileAncestorFileDescendantDb.ancestor_id,
                    insert_file_db_cte.c.id.label("descendant_id"),
                    case(
                        (FileAncestorFileDescendantDb.descendant_path == ".", name),
                        else_=(FileAncestorFileDescendantDb.descendant_path + "/" + name),
                    ).label("descendant_path"),
                    (FileAncestorFileDescendantDb.descendant_depth + 1).label("descendant_depth"),
                ).select_from(
                    FileAncestorFileDescendantDb, insert_file_db_cte
                ).where(FileAncestorFileDescendantDb.descendant_id == parent_id),
            ),
        ).cte()
    )  # fmt: skip
    select_file_db_with_parent_id_and_name_query = (
        select(
            insert_file_db_cte.c.id,
            insert_file_db_cte.c.type,
            literal(None).label("parent_id"),
            literal(None).label("name"),
        )
        .add_cte(insert_file_db_cte)
        .add_cte(insert_share_db_cte)
        .add_cte(insert_ancestors_db_cte)
    )
    file_db_with_parent_id_and_name_row = (
        (await connection.execute(select_file_db_with_parent_id_and_name_query))
        .mappings()
        .one()
    )
    file_db_with_parent_id_and_name = (
        FileDb(
            id=file_db_with_parent_id_and_name_row["id"],
            type=FileType(file_db_with_parent_id_and_name_row["type"]),
        ),
        _FileParentIdAndName(
            parent_id=file_db_with_parent_id_and_name_row["parent_id"],
            name=file_db_with_parent_id_and_name_row["name"],
        ),
    )
    (file,) = _make_files((file_db_with_parent_id_and_name,))

    yield file

    await connection.commit()


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


@asynccontextmanager
async def _move_file(
    id_: UUID,
    new_parent_id: UUID,
    new_name: FileName,
    /,
    *,
    connection: AsyncConnection,
) -> AsyncIterator[File]:
    select_descendants_db_cte = (
        select(
            FileAncestorFileDescendantDb.descendant_id,
            FileAncestorFileDescendantDb.descendant_path,
            FileAncestorFileDescendantDb.descendant_depth,
        )
        .where(FileAncestorFileDescendantDb.ancestor_id == id_)
        .cte()
    )
    delete_old_descendant_ancestors_db_cte = (
        delete(FileAncestorFileDescendantDb)
        .where(FileAncestorFileDescendantDb.descendant_id == select_descendants_db_cte.c.descendant_id)
        .where(FileAncestorFileDescendantDb.descendant_depth > select_descendants_db_cte.c.descendant_depth)
        .cte()
    )  # fmt: skip
    insert_new_descendant_ancestors_db_cte = (
        insert(FileAncestorFileDescendantDb)
        .from_select(
            ["ancestor_id", "descendant_id", "descendant_path", "descendant_depth"],
            select(
                FileAncestorFileDescendantDb.ancestor_id,
                select_descendants_db_cte.c.descendant_id,
                case(
                    (and_(FileAncestorFileDescendantDb.descendant_path == ".", select_descendants_db_cte.c.descendant_path == "."), new_name),
                    (and_(FileAncestorFileDescendantDb.descendant_path == ".", select_descendants_db_cte.c.descendant_path != "."), literal(new_name) + "/" + select_descendants_db_cte.c.descendant_path),
                    (and_(FileAncestorFileDescendantDb.descendant_path != ".", select_descendants_db_cte.c.descendant_path == "."), FileAncestorFileDescendantDb.descendant_path + "/" + new_name),
                    else_=(FileAncestorFileDescendantDb.descendant_path + "/" + new_name + "/" + select_descendants_db_cte.c.descendant_path),
                ).label("descendant_path"),
                (FileAncestorFileDescendantDb.descendant_depth + select_descendants_db_cte.c.descendant_depth + 1).label("descendant_depth"),
            )
            .select_from(FileAncestorFileDescendantDb, select_descendants_db_cte)
            .where(FileAncestorFileDescendantDb.descendant_id == new_parent_id)
        )
        .cte()
    )  # fmt: skip
    select_file_db_with_parent_id_and_name_query = (
        select(
            select_descendants_db_cte.c.descendant_id.label("id"),
            FileDb.type,
            literal(None).label("parent_id"),
            literal(None).label("name"),
        )
        .select_from(select_descendants_db_cte)
        .outerjoin(FileDb, select_descendants_db_cte.c.descendant_id == FileDb.id)
        .where(select_descendants_db_cte.c.descendant_id == id_)
        .add_cte(select_descendants_db_cte)
        .add_cte(delete_old_descendant_ancestors_db_cte)
        .add_cte(insert_new_descendant_ancestors_db_cte)
    )
    file_db_with_parent_id_and_name_row = (
        (await connection.execute(select_file_db_with_parent_id_and_name_query))
        .mappings()
        .one()
    )
    file_db_with_parent_id_and_name = (
        FileDb(
            id=file_db_with_parent_id_and_name_row["id"],
            type=FileType(file_db_with_parent_id_and_name_row["type"]),
        ),
        _FileParentIdAndName(
            parent_id=file_db_with_parent_id_and_name_row["parent_id"],
            name=file_db_with_parent_id_and_name_row["name"],
        ),
    )
    (file,) = _make_files((file_db_with_parent_id_and_name,))

    yield file

    await connection.commit()


@asynccontextmanager
async def _remove_file(
    id_: UUID, /, *, connection: AsyncConnection
) -> AsyncIterator[File]:
    fafd1 = aliased(FileAncestorFileDescendantDb)
    fafd2 = aliased(FileAncestorFileDescendantDb)
    select_descendant_files_db_with_parent_id_and_name_and_depth_cte = (
        select(
            FileDb.id,
            FileDb.type,
            case((fafd1.descendant_depth > 0, fafd2.ancestor_id), else_=literal(None)).label("parent_id"),
            case((fafd1.descendant_depth > 0, fafd2.descendant_path), else_=literal(None)).label("name"),
        )
        # Select descendants (the descendants include the file itself)
        .select_from(fafd1)
        .where(fafd1.ancestor_id == id_)
        # Select file for each descendant (should exist)
        .outerjoin(FileDb, fafd1.descendant_id == FileDb.id)
        # Select parent ID and name for each descendant if exists
        .outerjoin(fafd2, (fafd1.descendant_id == fafd2.descendant_id) & (fafd2.descendant_depth == 1))
        .cte()
    )  # fmt: skip
    delete_descendant_ancestors_db_cte = (
        delete(FileAncestorFileDescendantDb)
        .where(
            FileAncestorFileDescendantDb.descendant_id
            == select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.id
        )
        .cte()
    )
    delete_descendant_shares_db_cte = (
        delete(FileShareDb)
        .where(
            FileShareDb.file_id
            == select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.id
        )
        .cte()
    )
    delete_descendant_files_db_cte = (
        delete(FileDb)
        .where(
            FileDb.id
            == select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.id
        )
        .cte()
    )
    select_descendant_files_db_with_parent_id_and_name_query = (
        select(
            select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.id,
            select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.type,
            select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.parent_id,
            select_descendant_files_db_with_parent_id_and_name_and_depth_cte.c.name,
        )
        .add_cte(select_descendant_files_db_with_parent_id_and_name_and_depth_cte)
        .add_cte(delete_descendant_ancestors_db_cte)
        .add_cte(delete_descendant_shares_db_cte)
        .add_cte(delete_descendant_files_db_cte)
    )  # fmt: skip
    descendant_files_db_with_parent_id_and_name_rows = (
        (await connection.execute(select_descendant_files_db_with_parent_id_and_name_query))
        .mappings()
        .all()
    )  # fmt: skip
    descendant_files_db_with_parent_id_and_name = [
        (
            FileDb(id=row["id"], type=FileType(row["type"])),
            _FileParentIdAndName(parent_id=row["parent_id"], name=row["name"]),
        )
        for row in descendant_files_db_with_parent_id_and_name_rows
    ]
    (file,) = _make_files(descendant_files_db_with_parent_id_and_name)

    yield file

    await connection.commit()


class _FileParentIdAndName(NamedTuple):
    parent_id: UUID
    name: FileName


def _make_files(
    files_db_with_parent_id_and_name: Iterable[
        tuple[FileDb, _FileParentIdAndName | None]
    ],
) -> list[File]:
    """
    Makes tree-like files from edge-like database rows.

    If it is possible to tell if a file has content based solely on the database rows,
    the file will have content, otherwise the file's content will be None. Notably, a
    directory without content files will have a None content instead of an empty
    content because it is impossible to tell None content and empty content apart having
    only database rows.
    """

    # Prepare maps and sets. ids is an ad hoc ordered set needed to collect all
    # occurring file IDs and respect the original order of files.

    id_to_file_db: dict[UUID, FileDb] = {}
    parent_id_to_children: defaultdict[UUID, list[tuple[FileName, UUID]]] = defaultdict(
        list
    )
    child_ids: set[UUID] = set()
    ids: OrderedDict[UUID, bool] = OrderedDict()

    for file_db, parent_id_and_name in files_db_with_parent_id_and_name:
        if parent_id_and_name:
            parent_id, name = parent_id_and_name
            parent_id_to_children[parent_id].append((name, file_db.id))
            child_ids.add(file_db.id)
            ids[parent_id] = True

        id_to_file_db[file_db.id] = file_db
        ids[file_db.id] = True

    # Validate maps and sets.

    for id_ in ids:
        if id_ not in id_to_file_db:
            raise ValueError("File must have 'FileDb'")

    # Prepare root IDs - IDs of files that aren't children of other files in the current
    # context.

    root_ids: list[UUID] = []

    for id_ in ids:
        if id_ not in child_ids:
            root_ids.append(id_)

    # Make files using iterative DFS since in order to build parents, their children
    # need to be built first.

    id_to_file: dict[UUID, File] = {}
    stack: list[UUID] = root_ids.copy()

    while stack and (id_ := stack.pop()):
        children = parent_id_to_children[id_]

        # Ensure that children are built before their parents.

        not_made_child_ids: list[UUID] = []
        for _, child_id in children:
            if child_id not in id_to_file:
                not_made_child_ids.append(child_id)

        if not_made_child_ids:
            stack.append(id_)
            stack.extend(not_made_child_ids)
            continue

        # Make directory content if file has children.

        directory_content_files: list[DirectoryContentFile] = []
        for child_name, child_id in children:
            child_file = id_to_file[child_id]
            directory_content_file = DirectoryContentFile(
                name=child_name, file=child_file
            )
            directory_content_files.append(directory_content_file)
        directory_content = (
            DirectoryContent(
                count_=len(directory_content_files),
                items=directory_content_files,
            )
            if directory_content_files
            else None
        )

        # Make file.

        file: File
        file_db = id_to_file_db[id_]
        file_type = FileType(file_db.type)
        match file_type:
            case FileType.REGULAR:
                if directory_content:
                    raise ValueError("Regular file can't have directory content")
                file = Regular(id=file_db.id, type=file_type)
            case FileType.DIRECTORY:
                file = Directory(
                    id=file_db.id, type=file_type, content=directory_content
                )
            case _:
                assert_never(file_type)

        id_to_file[id_] = file

    # Return root files only.

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
