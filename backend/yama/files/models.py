from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, NamedTuple, TypeAlias
from uuid import UUID

from fastapi import UploadFile
from pydantic import AfterValidator, ValidatorFunctionWrapHandler, WrapValidator
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.files.settings import MAX_FILE_NAME_LENGTH, MAX_FILE_PATH_LENGTH
from yama.model.models import ModelBase


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


class FileShareType(str, Enum):
    READ = "read"
    WRITE = "write"
    SHARE = "share"


class RegularContent(NamedTuple):
    physical_path: Path


class Regular(NamedTuple):
    id: UUID
    type: Literal[FileType.REGULAR]
    content: RegularContent | None = None


class DirectoryContentFile(NamedTuple):
    name: FileName
    file: "File"


class DirectoryContent(NamedTuple):
    count_: int
    items: list[DirectoryContentFile]


class Directory(NamedTuple):
    id: UUID
    type: Literal[FileType.DIRECTORY]
    content: DirectoryContent | None = None


File: TypeAlias = Regular | Directory


class RegularContentOut(ModelBase):
    url: str


class RegularOut(ModelBase):
    id: UUID
    type: Literal[FileType.REGULAR]
    content: RegularContentOut | None = None


class DirectoryContentFileOut(ModelBase):
    name: FileName
    file: "FileOut"


class DirectoryContentOut(ModelBase):
    count: int
    items: list[DirectoryContentFileOut]


class DirectoryOut(ModelBase):
    id: UUID
    type: Literal[FileType.DIRECTORY]
    content: DirectoryContentOut | None = None


FileOut: TypeAlias = RegularOut | DirectoryOut


class RegularContentWrite(NamedTuple):
    upload_file: UploadFile


class RegularWrite(NamedTuple):
    type: Literal[FileType.REGULAR]
    content: RegularContentWrite


class DirectoryWrite(NamedTuple):
    type: Literal[FileType.DIRECTORY]


FileWrite: TypeAlias = RegularWrite | DirectoryWrite


class FileTypeDb(TableBase):
    __tablename__ = "file_types"

    type: Mapped[str] = mapped_column(primary_key=True)


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
    descendant_path: Mapped[str]
    descendant_depth: Mapped[int]


class FileShareTypeDb(TableBase):
    __tablename__ = "file_share_types"

    type: Mapped[str] = mapped_column(primary_key=True)


class FileShareDb(TableBase):
    __tablename__ = "file_shares"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("file_share_types.type"))
    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
