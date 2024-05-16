from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    TypeAdapter,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import BaseTable
from yama.file.driver.utils import AsyncReadable
from yama.file.settings import MAX_FILE_NAME_LENGTH, MAX_FILE_PATH_LENGTH


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
FilePathAdapter: TypeAdapter[FilePath] = TypeAdapter(FilePath)


class FileType(str, Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"


class FileShareType(str, Enum):
    READ = "read"
    WRITE = "write"
    SHARE = "share"


@dataclass(frozen=True)
class Regular:
    id: UUID
    type: Literal[FileType.REGULAR]


@dataclass(frozen=True)
class DirectoryContentFile:
    name: FileName
    file: "File"


@dataclass(frozen=True)
class DirectoryContent:
    files: list[DirectoryContentFile]


@dataclass(frozen=True)
class Directory:
    id: UUID
    type: Literal[FileType.DIRECTORY]
    content: DirectoryContent


File: TypeAlias = Regular | Directory


class RegularContentOut(BaseModel):
    url: str


class RegularOut(BaseModel):
    id: UUID
    type: Literal[FileType.REGULAR]
    content: RegularContentOut | None = None


class DirectoryContentFileOut(BaseModel):
    name: FileName
    file: "FileOut"


class DirectoryContentOut(BaseModel):
    files: list[DirectoryContentFileOut]


class DirectoryOut(BaseModel):
    id: UUID
    type: Literal[FileType.DIRECTORY]
    content: DirectoryContentOut | None = None


FileOut: TypeAlias = RegularOut | DirectoryOut


@dataclass(frozen=True)
class RegularContentWrite:
    stream: AsyncReadable


@dataclass(frozen=True)
class RegularWrite:
    type: Literal[FileType.REGULAR]
    content: RegularContentWrite


@dataclass(frozen=True)
class DirectoryWrite:
    type: Literal[FileType.DIRECTORY]


FileWrite: TypeAlias = RegularWrite | DirectoryWrite


class FileTypeDb(BaseTable):
    __tablename__ = "file_types"

    type: Mapped[str] = mapped_column(primary_key=True)


class FileDb(BaseTable):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("file_types.type"))


class FileAncestorFileDescendantDb(BaseTable):
    __tablename__ = "file_ancestors_file_descendants"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    ancestor_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"))
    descendant_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"))
    descendant_path: Mapped[str]
    descendant_depth: Mapped[int]


class FileShareTypeDb(BaseTable):
    __tablename__ = "file_share_types"

    type: Mapped[str] = mapped_column(primary_key=True)


class FileShareDb(BaseTable):
    __tablename__ = "file_shares"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("file_share_types.type"))
    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
