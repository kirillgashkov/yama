from collections import OrderedDict, defaultdict, deque
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import NamedTuple, assert_never
from uuid import UUID

from sqlalchemy import and_, case, delete, insert, literal, select, union
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import aliased
from typing_extensions import override

from yama.file.driver.utils import Driver
from yama.file.models import (
    Directory,
    DirectoryContent,
    DirectoryContentFile,
    DirectoryWrite,
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
    RegularWrite,
)
from yama.file.settings import Settings
from yama.user.models import UserAncestorUserDescendantDb


async def read_file(
    path: FilePath,
    /,
    *,
    max_depth: int | None,
    user_id: UUID,
    working_file_id: UUID,
    settings: Settings,
    connection: AsyncConnection,
) -> File:
    id_ = await _path_to_id(
        path,
        root_file_id=settings.root_file_id,
        working_file_id=working_file_id,
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

    file = await _get_file(id_, max_depth=max_depth, connection=connection)

    return file


async def write_file(
    file_write: FileWrite,
    path: FilePath,
    /,
    *,
    exist_ok: bool = True,
    user_id: UUID,
    working_file_id: UUID,
    settings: Settings,
    connection: AsyncConnection,
    driver: Driver,
) -> File:
    parent_id, id_ = await _path_to_parent_id_and_id_or_none(
        path,
        root_file_id=settings.root_file_id,
        working_file_id=working_file_id,
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

    connection_to_commit: AsyncConnection | None = None
    if id_ is not None:
        file = await _get_file(id_, max_depth=0, connection=connection)

        if not exist_ok:
            raise FilesFileExistsError(id_)

        if file.type != file_write.type:
            match file.type:
                case FileType.REGULAR:
                    raise FilesNotADirectoryError(file.id)
                case FileType.DIRECTORY:
                    raise FilesIsADirectoryError(file.id)
                case _:
                    assert_never(file.type)
    else:
        name = _path_to_some_name(path)

        file, connection_to_commit = await _add_file(
            parent_id,
            name,
            type_=file_write.type,
            user_id=user_id,
            connection=connection,
        )

    match file_write:
        case RegularWrite(content=content):
            _ = await driver.write_regular_content(
                content.stream,
                file.id,
                chunk_size=settings.chunk_size,
                max_file_size=settings.max_file_size,
            )
        case DirectoryWrite():
            ...
        case _:
            assert_never(file_write)

    if connection_to_commit is not None:
        await connection_to_commit.commit()

    return file


async def remove_file(
    path: FilePath,
    /,
    *,
    user_id: UUID,
    working_file_id: UUID,
    settings: Settings,
    connection: AsyncConnection,
    driver: Driver,
) -> File:
    id_ = await _path_to_id(
        path,
        root_file_id=settings.root_file_id,
        working_file_id=working_file_id,
        connection=connection,
    )

    await _check_share_for_file_and_user(
        allowed_types=[
            FileShareType.WRITE,
            FileShareType.SHARE,
        ],
        file_id=id_,
        user_id=user_id,
        connection=connection,
    )

    file, connection_to_commit = await _remove_file(id_, connection=connection)

    for descendant_file in _file_to_descendant_files(file):
        match descendant_file.type:
            case FileType.REGULAR:
                await driver.remove_regular_content(descendant_file.id)
            case FileType.DIRECTORY:
                ...
            case _:
                assert_never(descendant_file.type)

    file_with_depth_0 = _file_to_file_with_depth_0(file)

    await connection_to_commit.commit()

    return file_with_depth_0


async def move_file(
    src_path: FilePath,
    dst_path: FilePath,
    /,
    *,
    user_id: UUID,
    working_file_id: UUID,
    settings: Settings,
    connection: AsyncConnection,
) -> File:
    src_parent_id, src_id = await _path_to_parent_id_and_id(
        src_path,
        root_file_id=settings.root_file_id,
        working_file_id=working_file_id,
        connection=connection,
    )
    dst_parent_id = await _path_to_parent_id(
        dst_path,
        root_file_id=settings.root_file_id,
        working_file_id=working_file_id,
        connection=connection,
    )
    dst_name = _path_to_some_name(dst_path)

    await _check_share_for_file_and_user(
        allowed_types=[
            FileShareType.WRITE,
            FileShareType.SHARE,
        ],
        file_id=src_parent_id,
        user_id=user_id,
        connection=connection,
    )
    await _check_share_for_file_and_user(
        allowed_types=[
            FileShareType.WRITE,
            FileShareType.SHARE,
        ],
        file_id=dst_parent_id,
        user_id=user_id,
        connection=connection,
    )

    file, connection_to_commit = await _move_file(
        src_id, dst_parent_id, dst_name, connection=connection
    )

    await connection_to_commit.commit()

    return file


async def _add_file(
    parent_id: UUID,
    name: FileName,
    /,
    *,
    type_: FileType,
    user_id: UUID,
    connection: AsyncConnection,
) -> tuple[File, AsyncConnection]:
    """
    Returns the added file and a connection with uncommitted transaction.
    """
    insert_file_db_cte = insert(FileDb).values(type=type_.value).returning(FileDb).cte()
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
        )
        .returning(FileAncestorFileDescendantDb)
        .cte()
    )  # fmt: skip
    select_file_db_with_parent_id_and_name_query = (
        select(
            insert_ancestors_db_cte.c.ancestor_id.label("id"),
            insert_file_db_cte.c.type,
            literal(None).label("parent_id"),
            literal(None).label("name"),
        )
        .select_from(insert_ancestors_db_cte)
        .outerjoin(insert_file_db_cte, insert_ancestors_db_cte.c.ancestor_id == insert_file_db_cte.c.id)
        .add_cte(insert_file_db_cte)
        .add_cte(insert_share_db_cte)
        .add_cte(insert_ancestors_db_cte)
    )  # fmt: skip

    # FIXME: Handle IntegrityError about "fafd_parent_id_child_name_uidx" that can be
    # caused by insert_ancestors_db_cte.
    file_db_with_parent_id_and_name_row = (
        (await connection.execute(select_file_db_with_parent_id_and_name_query))
        .mappings()
        .one_or_none()
    )
    if file_db_with_parent_id_and_name_row is None:
        raise FilesFileNotFoundError(parent_id)

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

    return file, connection


async def _get_file(
    id_: UUID, *, max_depth: int | None, connection: AsyncConnection
) -> File:
    descendant_alias = aliased(FileAncestorFileDescendantDb)
    descendant_file_alias = aliased(FileDb)
    descendant_parent_alias = aliased(FileAncestorFileDescendantDb)

    if max_depth is not None and max_depth >= 0 and max_depth <= 1:
        query = (
            select(
                descendant_alias.descendant_id.label("id"),
                descendant_file_alias.type,
                case((descendant_alias.descendant_depth > 0, descendant_alias.ancestor_id), else_=literal(None)).label("parent_id"),
                case((descendant_alias.descendant_depth > 0, descendant_alias.descendant_path), else_=literal(None)).label("name"),
            )
            .select_from(descendant_alias)
            .outerjoin(descendant_file_alias, descendant_alias.descendant_id == descendant_file_alias.id)
            .where((descendant_alias.ancestor_id == id_) & (descendant_alias.descendant_depth <= max_depth))
        )  # fmt: skip
    elif max_depth is None or max_depth >= 2:
        query = (
            select(
                descendant_alias.descendant_id.label("id"),
                descendant_file_alias.type,
                case((descendant_alias.descendant_depth > 0, descendant_parent_alias.ancestor_id), else_=literal(None)).label("parent_id"),
                case((descendant_alias.descendant_depth > 0, descendant_parent_alias.descendant_path), else_=literal(None)).label("name"),
            )
            .select_from(descendant_alias)
            .outerjoin(descendant_file_alias, descendant_alias.descendant_id == descendant_file_alias.id)
            .outerjoin(descendant_parent_alias, (descendant_alias.descendant_id == descendant_parent_alias.descendant_id) & (descendant_parent_alias.descendant_depth == 1))
            .where(descendant_alias.ancestor_id == id_)
        )  # fmt: skip
        if max_depth is not None:
            query = query.where(descendant_alias.descendant_depth <= max_depth)
    else:
        raise ValueError("Invalid max_depth")

    descendant_files_db_with_parent_id_and_name_rows = (
        (await connection.execute(query)).mappings().all()
    )
    if not descendant_files_db_with_parent_id_and_name_rows:
        raise FilesFileNotFoundError(id_)

    descendant_files_db_with_parent_id_and_name = [
        (
            FileDb(id=row["id"], type=FileType(row["type"])),
            _FileParentIdAndName(parent_id=row["parent_id"], name=row["name"]),
        )
        for row in descendant_files_db_with_parent_id_and_name_rows
    ]
    (file,) = _make_files(descendant_files_db_with_parent_id_and_name)

    return file


async def _move_file(
    id_: UUID,
    new_parent_id: UUID,
    new_name: FileName,
    /,
    *,
    connection: AsyncConnection,
) -> tuple[File, AsyncConnection]:
    """
    Returns the moved file and a connection with uncommitted transaction.
    """
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
            .select_from(select_descendants_db_cte, FileAncestorFileDescendantDb)
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
        .where(select_descendants_db_cte.c.descendant_id == id_)
        .outerjoin(FileDb, select_descendants_db_cte.c.descendant_id == FileDb.id)
        .add_cte(select_descendants_db_cte)
        .add_cte(delete_old_descendant_ancestors_db_cte)
        .add_cte(insert_new_descendant_ancestors_db_cte)
    )

    # FIXME: Handle IntegrityError about "fafd_parent_id_child_name_uidx" that can be
    # caused by insert_new_descendant_ancestors_db_cte.
    file_db_with_parent_id_and_name_row = (
        (await connection.execute(select_file_db_with_parent_id_and_name_query))
        .mappings()
        .one_or_none()
    )
    if file_db_with_parent_id_and_name_row is None:
        raise FilesFileNotFoundError(id_)

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

    return file, connection


async def _remove_file(
    id_: UUID, /, *, connection: AsyncConnection
) -> tuple[File, AsyncConnection]:
    """
    Returns the removed file and a connection with uncommitted transaction.
    """
    fafd1 = aliased(FileAncestorFileDescendantDb)
    fafd2 = aliased(FileAncestorFileDescendantDb)
    select_descendant_files_db_with_parent_id_and_name_cte = (
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
            == select_descendant_files_db_with_parent_id_and_name_cte.c.id
        )
        .cte()
    )
    delete_descendant_shares_db_cte = (
        delete(FileShareDb)
        .where(
            FileShareDb.file_id
            == select_descendant_files_db_with_parent_id_and_name_cte.c.id
        )
        .cte()
    )
    delete_descendant_files_db_cte = (
        delete(FileDb)
        .where(FileDb.id == select_descendant_files_db_with_parent_id_and_name_cte.c.id)
        .cte()
    )
    select_descendant_files_db_with_parent_id_and_name_query = (
        select(
            select_descendant_files_db_with_parent_id_and_name_cte.c.id,
            select_descendant_files_db_with_parent_id_and_name_cte.c.type,
            select_descendant_files_db_with_parent_id_and_name_cte.c.parent_id,
            select_descendant_files_db_with_parent_id_and_name_cte.c.name,
        )
        .add_cte(select_descendant_files_db_with_parent_id_and_name_cte)
        .add_cte(delete_descendant_ancestors_db_cte)
        .add_cte(delete_descendant_shares_db_cte)
        .add_cte(delete_descendant_files_db_cte)
    )  # fmt: skip

    descendant_files_db_with_parent_id_and_name_rows = (
        (await connection.execute(select_descendant_files_db_with_parent_id_and_name_query))
        .mappings()
        .all()
    )  # fmt: skip
    if not descendant_files_db_with_parent_id_and_name_rows:
        raise FilesFileNotFoundError(id_)

    descendant_files_db_with_parent_id_and_name = [
        (
            FileDb(id=row["id"], type=FileType(row["type"])),
            _FileParentIdAndName(parent_id=row["parent_id"], name=row["name"]),
        )
        for row in descendant_files_db_with_parent_id_and_name_rows
    ]
    (file,) = _make_files(descendant_files_db_with_parent_id_and_name)

    return file, connection


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

        # Make file.

        file: File
        file_db = id_to_file_db[id_]
        file_type = FileType(file_db.type)
        match file_type:
            case FileType.REGULAR:
                if directory_content_files:
                    raise ValueError("Regular file can't have directory content files")
                file = Regular(id=file_db.id, type=file_type)
            case FileType.DIRECTORY:
                file = Directory(
                    id=file_db.id,
                    type=file_type,
                    content=DirectoryContent(files=directory_content_files),
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


def _file_to_descendant_files(file: File, /) -> Iterable[File]:
    queue: deque[File] = deque([file])

    while queue and (file := queue.pop()):
        yield file

        match file:
            case Regular():
                ...
            case Directory():
                for content_file in file.content.files:
                    queue.append(content_file.file)
            case _:
                assert_never(file)


def _file_to_file_with_depth_0(file: File, /) -> File:
    file_with_depth_0: File
    match file:
        case Regular():
            file_with_depth_0 = file
        case Directory():
            file_with_depth_0 = Directory(
                id=file.id, type=file.type, content=DirectoryContent(files=[])
            )
        case _:
            assert_never(file)

    return file_with_depth_0


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


async def _path_to_id(
    path: FilePath,
    /,
    *,
    root_file_id: UUID,
    working_file_id: UUID,
    connection: AsyncConnection,
) -> UUID:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, root_file_id=root_file_id, working_file_id=working_file_id
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
    root_file_id: UUID,
    working_file_id: UUID,
    connection: AsyncConnection,
) -> UUID:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, root_file_id=root_file_id, working_file_id=working_file_id
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
    root_file_id: UUID,
    working_file_id: UUID,
    connection: AsyncConnection,
) -> tuple[UUID, UUID | None]:
    ancestor_id, descendant_path = _path_to_ancestor_id_and_descendant_path(
        path, root_file_id=root_file_id, working_file_id=working_file_id
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


async def _path_to_parent_id_and_id(
    path: FilePath,
    /,
    *,
    root_file_id: UUID,
    working_file_id: UUID,
    connection: AsyncConnection,
) -> tuple[UUID, UUID]:
    parent_id, id_ = await _path_to_parent_id_and_id_or_none(
        path,
        root_file_id=root_file_id,
        working_file_id=working_file_id,
        connection=connection,
    )
    if id_ is None:
        raise FilesFileNotFoundError(parent_id, PurePosixPath(path.name))

    return parent_id, id_


def _path_to_some_name(path: FilePath, /) -> FileName:
    name = path.name
    if not name:
        raise ValueError("Cannot get file name from path without names")

    return name


def _path_to_ancestor_id_and_descendant_path(
    path: FilePath,
    /,
    *,
    root_file_id: UUID,
    working_file_id: UUID,
) -> tuple[UUID, FilePath]:
    if path.is_absolute():
        ancestor_id = root_file_id
        descendant_path = path.relative_to("/")
    else:
        ancestor_id = working_file_id
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
        PurePosixPath(row["descendant_path"]): row["descendant_id"]  # pyright: ignore[reportAny]  # basedpyright-specific
        for row in descendant_path_to_id_rows
    }  # HACK: Implicit type cast

    return descendant_path_to_id


class FilesFileError(Exception):
    def __init__(
        self, ancestor_id: UUID, descendant_path: FilePath | None = None, /
    ) -> None:
        super().__init__()
        if descendant_path is None:
            descendant_path = PurePosixPath(".")
        self.ancestor_id = ancestor_id
        self.descendant_path: FilePath = descendant_path

    @override
    def __str__(self) -> str:
        return f"'{self.descendant_path}' relative to {self.ancestor_id}"


class FilesFileExistsError(FilesFileError): ...


class FilesFileNotFoundError(FilesFileError): ...


class FilesIsADirectoryError(FilesFileError): ...


class FilesNotADirectoryError(FilesFileError): ...


class FilesPermissionError(FilesFileError): ...
