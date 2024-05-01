from collections.abc import Sequence
from pathlib import Path
from typing import assert_never
from uuid import UUID

import aiofiles
from fastapi import UploadFile
from sqlalchemy import and_, case, delete, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.file._models import (
    DirectoryCreateTuple,
    DirectoryEntryReadTuple,
    DirectoryReadTuple,
    DirectoryUpdateTuple,
    File,
    FileAncestorFileDescendant,
    FileCreateTuple,
    FilePath,
    FileReadTuple,
    FileTypeEnum,
    FileTypeEnumAdapter,
    FileUpdateTuple,
    RegularCreateTuple,
    RegularReadTuple,
    RegularUpdateTuple,
)


class UploadFileTooLargeError(Exception): ...


class FilesFileError(Exception):
    def __init__(self, path: FilePath) -> None:
        self.path = path

    def __str__(self) -> str:
        return f"'{self.path}'"


class FilesFileExistsError(FilesFileError): ...


class FilesFileNotFoundError(FilesFileError): ...


class FilesIsADirectoryError(FilesFileError): ...


class FilesNotADirectoryError(FilesFileError): ...


# class FilesPermissionError(FilesFileError):
#     ...


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
        ).where(File.type == type_.value)
    file_exists_subquery = file_exists_subquery_base.exists()

    query = select(file_exists_subquery)
    return (await connection.execute(query)).scalar_one()


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

    insert_file_query = insert(File).values(type=file_in.type.value).returning(File)
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
        case RegularCreateTuple(content=content):
            await _write_file(
                content,
                file.id,
                chunk_size=upload_chunk_size,
                files_dir=files_dir,
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
    file = await _get_file_by_path(
        path,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    )
    file_type = FileTypeEnumAdapter.validate_python(file.type)

    if type_ is not None and type_ != file_type:
        match type_:
            case FileTypeEnum.DIRECTORY:
                raise FilesNotADirectoryError(path)
            case FileTypeEnum.REGULAR:
                raise FilesIsADirectoryError(path)
            case _:
                assert_never(type_)

    match file_type:
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
                    id=row["id"],
                    type=FileTypeEnumAdapter.validate_python(row["type"]),
                    name=row["descendant_path"],
                )
                for row in directory_entries_rows
            ]
            return DirectoryReadTuple(
                id=file.id, type=file_type, content=directory_entries
            )
        case FileTypeEnum.REGULAR:
            return RegularReadTuple(
                id=file.id,
                type=file_type,
                content_physical_path=_id_to_physical_path(
                    file.id, files_dir=files_dir
                ),
            )
        case _:
            assert_never(file_type)


# FIXME: Add security
async def update_file(
    path: FilePath,
    new_path: FilePath | None = None,
    /,
    *,
    file_in: FileUpdateTuple | None = None,
    user_id: UUID,
    working_dir_id: UUID,
    files_dir: Path,
    root_dir_id: UUID,
    upload_chunk_size: int,
    upload_max_file_size: int,
    connection: AsyncConnection,
) -> UUID:
    file = await _get_file_by_path(
        path,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    )
    file_type = FileTypeEnumAdapter.validate_python(file.type)

    if file_in is not None and file_in.type != file_type:
        match file_in.type:
            case FileTypeEnum.DIRECTORY:
                raise FilesNotADirectoryError(path)
            case FileTypeEnum.REGULAR:
                raise FilesIsADirectoryError(path)
            case _:
                assert_never(file_in.type)

    if new_path is not None:
        if not await file_exists(
            new_path.parent,
            type_=FileTypeEnum.DIRECTORY,
            user_id=user_id,
            working_dir_id=working_dir_id,
            root_dir_id=root_dir_id,
            connection=connection,
        ):
            raise FilesFileNotFoundError(new_path.parent)
        if await file_exists(
            new_path,
            user_id=user_id,
            working_dir_id=working_dir_id,
            root_dir_id=root_dir_id,
            connection=connection,
        ):
            raise FilesFileExistsError(new_path)

        new_parent = await _get_file_by_path(
            new_path.parent,
            working_dir_id=working_dir_id,
            root_dir_id=root_dir_id,
            connection=connection,
        )

        # fmt: off
        select_descendants_cte = (  # Includes the relationship of the file itself
            select(
                FileAncestorFileDescendant.descendant_id,
                FileAncestorFileDescendant.descendant_path,
                FileAncestorFileDescendant.descendant_depth,
            )
            .where(FileAncestorFileDescendant.ancestor_id == file.id)
            .cte()
        )
        select_old_ancestors_cte = (
            select(
                FileAncestorFileDescendant.ancestor_id,
                FileAncestorFileDescendant.descendant_id,
            )
            .select_from(FileAncestorFileDescendant, select_descendants_cte)
            .where(FileAncestorFileDescendant.descendant_id == select_descendants_cte.c.descendant_id)
            .where(FileAncestorFileDescendant.descendant_depth > select_descendants_cte.c.descendant_depth)
            .with_for_update(nowait=True)  # TODO: Handle exception
            .cte()
        )
        select_new_ancestors_cte = (
            select(
                FileAncestorFileDescendant.ancestor_id,
                select_descendants_cte.c.descendant_id,
                (
                    case(
                        (
                            and_(FileAncestorFileDescendant.descendant_path == ".", select_descendants_cte.c.descendant_path == "."),
                            literal(new_path.name),
                        ),
                        (
                            and_(FileAncestorFileDescendant.descendant_path == ".", select_descendants_cte.c.descendant_path != "."),
                            literal(new_path.name) + "/" + select_descendants_cte.c.descendant_path,
                        ),
                        (
                            and_(FileAncestorFileDescendant.descendant_path != ".", select_descendants_cte.c.descendant_path == "."),
                            FileAncestorFileDescendant.descendant_path + "/" + literal(new_path.name),
                        ),
                        else_=(
                            FileAncestorFileDescendant.descendant_path + "/" + literal(new_path.name) + "/" + select_descendants_cte.c.descendant_path
                        ),
                    )
                    .label("descendant_path")
                ),
                (FileAncestorFileDescendant.descendant_depth + select_descendants_cte.c.descendant_depth + 1).label("descendant_depth"),
            )
            .select_from(FileAncestorFileDescendant, select_descendants_cte)
            .where(FileAncestorFileDescendant.descendant_id == new_parent.id)
            .cte()
        )
        delete_old_ancestors_cte = (
            delete(FileAncestorFileDescendant)
            .where(FileAncestorFileDescendant.ancestor_id == select_old_ancestors_cte.c.descendant_id)
            .where(FileAncestorFileDescendant.descendant_id == select_old_ancestors_cte.c.descendant_id)
            .where(FileAncestorFileDescendant.ancestor_id != select_new_ancestors_cte.c.descendant_id)
            .where(FileAncestorFileDescendant.descendant_id != select_new_ancestors_cte.c.descendant_id)
            .cte()
        )
        insert_new_ancestors_base = (
            insert(FileAncestorFileDescendant)
            .from_select(
                ["ancestor_id", "descendant_id", "descendant_path", "descendant_depth"],
                select(
                    select_new_ancestors_cte.c.ancestor_id,
                    select_new_ancestors_cte.c.descendant_id,
                    select_new_ancestors_cte.c.descendant_path,
                    select_new_ancestors_cte.c.descendant_depth,
                ),
            )
        )
        insert_new_ancestors_query = (
            insert_new_ancestors_base
            .on_conflict_do_update(
                index_elements=[
                    select_new_ancestors_cte.c.ancestor_id,
                    select_new_ancestors_cte.c.descendant_id,
                ],
                set_={
                    "descendant_path": insert_new_ancestors_base.excluded.descendant_path,
                    "descendant_depth": insert_new_ancestors_base.excluded.descendant_depth,
                },
            )
            .add_cte(select_descendants_cte)
            .add_cte(select_old_ancestors_cte)
            .add_cte(select_new_ancestors_cte)
            .add_cte(delete_old_ancestors_cte)
        )
        await connection.execute(insert_new_ancestors_query)
        # fmt: on

        await connection.commit()

    if file_in is not None:
        match file_in:
            case RegularUpdateTuple(content=content):
                if content is not None:
                    await _write_file(
                        content,
                        file.id,
                        chunk_size=upload_chunk_size,
                        files_dir=files_dir,
                        max_file_size=upload_max_file_size,
                    )
            case DirectoryUpdateTuple():
                ...
            case _:
                assert_never(file_in)

    return file.id


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
    file = await _get_file_by_path(
        path,
        working_dir_id=working_dir_id,
        root_dir_id=root_dir_id,
        connection=connection,
    )
    file_type = FileTypeEnumAdapter.validate_python(file.type)

    if type_ is not None and type_ != file_type:
        match type_:
            case FileTypeEnum.DIRECTORY:
                raise FilesNotADirectoryError(path)
            case FileTypeEnum.REGULAR:
                raise FilesIsADirectoryError(path)
            case _:
                assert_never(type_)

    delete_descendant_relationships_cte = (  # Includes the relationship of the file itself
        delete(FileAncestorFileDescendant)
        .where(FileAncestorFileDescendant.ancestor_id == file.id)
        .returning(FileAncestorFileDescendant.descendant_id)
        .cte()
    )
    delete_ancestor_relationships_cte = (  # Includes the relationships of the descendants
        delete(FileAncestorFileDescendant)
        .where(
            FileAncestorFileDescendant.descendant_id
            == delete_descendant_relationships_cte.c.descendant_id
        )
        .cte()
    )
    delete_files_cte = (
        delete(File)
        .where(File.id == delete_descendant_relationships_cte.c.descendant_id)
        .returning(File.id, File.type)
        .cte()
    )
    select_regular_file_ids_query = (
        select(delete_files_cte.c.id)
        .where(delete_files_cte.c.type == FileTypeEnum.REGULAR.value)
        .add_cte(delete_descendant_relationships_cte)
        .add_cte(delete_ancestor_relationships_cte)
        .add_cte(delete_files_cte)
    )
    regular_file_ids: Sequence[UUID] = (  # HACK: Implicit type cast
        (await connection.execute(select_regular_file_ids_query)).scalars().all()
    )

    await connection.commit()

    for regular_file_id in regular_file_ids:
        physical_path = _id_to_physical_path(regular_file_id, files_dir=files_dir)
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


async def _get_file_by_path(
    path: FilePath,
    /,
    *,
    working_dir_id: UUID,
    root_dir_id: UUID,
    connection: AsyncConnection,
) -> File:
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

    return File(**file_row)


async def _write_file(
    upload_file: UploadFile,
    id: UUID,
    /,
    *,
    chunk_size: int,
    files_dir: Path,
    max_file_size: int,
) -> int:
    files_dir.mkdir(parents=True, exist_ok=True)

    incomplete_path = _id_to_incomplete_physical_path(id, files_dir=files_dir)
    complete_path = _id_to_physical_path(id, files_dir=files_dir)

    file_size = 0
    async with aiofiles.open(incomplete_path, "wb") as f:
        while chunk := await upload_file.read(chunk_size):
            file_size += len(chunk)

            if file_size > max_file_size:
                incomplete_path.unlink(missing_ok=True)
                raise UploadFileTooLargeError()

            await f.write(chunk)

    incomplete_path.rename(complete_path)

    return file_size


def _id_to_physical_path(id: UUID, /, *, files_dir: Path) -> Path:
    return files_dir / id.hex


def _id_to_incomplete_physical_path(id: UUID, /, *, files_dir: Path) -> Path:
    return files_dir / (id.hex + ".incomplete")
