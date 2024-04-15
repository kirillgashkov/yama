from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, NamedTuple, Optional, TypeAlias
from uuid import UUID

from fastapi import UploadFile
from pydantic import AfterValidator, ValidatorFunctionWrapHandler, WrapValidator
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.files.settings import MAX_FILE_NAME_LENGTH, MAX_FILE_PATH_LENGTH


def _check_file_name(name: str) -> str:
    assert len(name.encode()) <= MAX_FILE_NAME_LENGTH, "File name is too long"
    assert name.isprintable(), "File name contains non-printable characters"
    assert "/" not in name, "File name contains '/'"
    assert name != "..", "File name '..' is not supported"
    return name


def _check_file_path(
    path_data: Any, handler: ValidatorFunctionWrapHandler
) -> PurePosixPath:
    assert isinstance(path_data, str), "File path is not a string"
    assert len(path_data.encode()) <= MAX_FILE_PATH_LENGTH, "File path is too long"

    path = handler(path_data)
    if not isinstance(path, PurePosixPath):
        raise RuntimeError("File path is not a PurePosixPath")

    if path.is_absolute():
        names = path.parts[1:]
    else:
        names = path.parts

    for name in names:
        _check_file_name(name)

    return path


def _normalize_file_path_root(path: PurePosixPath) -> PurePosixPath:
    # POSIX allows treating a path beginning with two slashes in an
    # implementation-defined manner which is respected by Python's pathlib by not
    # collapsing the two slashes into one. We treat such paths as absolute paths.
    if path.parts and path.parts[0] == "//":
        return PurePosixPath("/", *path.parts[1:])
    return path


FileName: TypeAlias = Annotated[str, AfterValidator(_check_file_name)]
FilePath: TypeAlias = Annotated[
    PurePosixPath,
    AfterValidator(_normalize_file_path_root),
    WrapValidator(_check_file_path),
]


class FileType(str, Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"


class ShareType(str, Enum):
    READ = "read"
    WRITE = "write"
    SHARE = "share"


class RegularRead(NamedTuple):
    id: UUID
    type: Literal[FileType.REGULAR]
    content_path: Path | None


class DirectoryRead(NamedTuple):
    id: UUID
    type: Literal[FileType.DIRECTORY]
    files: "dict[FileName, FileRead] | None"


FileRead: TypeAlias = RegularRead | DirectoryRead


class RegularWrite(NamedTuple):
    type: Literal[FileType.REGULAR]
    content_stream: UploadFile


class DirectoryWrite(NamedTuple):
    ...


FileWrite: TypeAlias = RegularWrite | DirectoryWrite


class FileShare(NamedTuple):
    ...


class FileTypeDb(TableBase):
    __tablename__ = "file_types"

    type: Mapped[str] = mapped_column(String, primary_key=True)


class FileDb(TableBase):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("file_types.type"))


class FileAncestorFileDescendantDb(TableBase):
    __tablename__ = "file_ancestors_file_descendants"

    ancestor_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"), primary_key=True)
    descendant_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id"), primary_key=True
    )
    descendant_name: Mapped[str]
    descendant_path: Mapped[str]
    descendant_depth: Mapped[int]


class ShareTypeDb(TableBase):
    __tablename__ = "share_types"

    type: Mapped[str] = mapped_column(String, primary_key=True)


class ShareDb(TableBase):
    __tablename__ = "shares"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("share_types.type"))
    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"))
    by_user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
