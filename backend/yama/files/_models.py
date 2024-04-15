from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, NamedTuple, TypeAlias
from uuid import UUID

from fastapi import UploadFile
from pydantic import (
    AfterValidator,
    TypeAdapter,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)
from sqlalchemy import ForeignKey, String, func
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
FileNameAdapter: TypeAdapter[FileName] = TypeAdapter(FileName)  # pyright: ignore [reportCallIssue, reportAssignmentType]

FilePath: TypeAlias = Annotated[
    PurePosixPath,
    AfterValidator(_normalize_file_path_root),
    WrapValidator(_check_file_path),
]
FilePathAdapter: TypeAdapter[FilePath] = TypeAdapter(FilePath)  # pyright: ignore [reportCallIssue, reportAssignmentType]


class FileTypeEnum(str, Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"


FileTypeEnumAdapter: TypeAdapter[FileTypeEnum] = TypeAdapter(FileTypeEnum)


class FileRead(ModelBase):
    id: UUID
    type: FileTypeEnum


class RegularReadDetail(ModelBase):
    id: UUID
    type: Literal[FileTypeEnum.REGULAR]
    content_url: str


class DirectoryReadDetail(ModelBase):
    id: UUID
    type: Literal[FileTypeEnum.DIRECTORY]
    files: dict[FileName, FileRead]


FileReadDetail: TypeAlias = RegularReadDetail | DirectoryReadDetail


class RegularCreateTuple(NamedTuple):
    content: UploadFile
    type: Literal[FileTypeEnum.REGULAR] = FileTypeEnum.REGULAR


class DirectoryCreateTuple(NamedTuple):
    type: Literal[FileTypeEnum.DIRECTORY] = FileTypeEnum.DIRECTORY


FileCreateTuple: TypeAlias = RegularCreateTuple | DirectoryCreateTuple


class RegularReadTuple(NamedTuple):
    id: UUID
    content_physical_path: Path
    type: Literal[FileTypeEnum.REGULAR] = FileTypeEnum.REGULAR


class DirectoryEntryReadTuple(NamedTuple):
    id: UUID
    type: FileTypeEnum
    name: FileName


class DirectoryReadTuple(NamedTuple):
    id: UUID
    content: list[DirectoryEntryReadTuple]
    type: Literal[FileTypeEnum.DIRECTORY] = FileTypeEnum.DIRECTORY


FileReadTuple: TypeAlias = RegularReadTuple | DirectoryReadTuple


class RegularUpdateTuple(NamedTuple):
    type: Literal[FileTypeEnum.REGULAR] = FileTypeEnum.REGULAR
    content: UploadFile | None = None


class DirectoryUpdateTuple(NamedTuple):
    type: Literal[FileTypeEnum.DIRECTORY] = FileTypeEnum.DIRECTORY


FileUpdateTuple: TypeAlias = RegularUpdateTuple | DirectoryUpdateTuple


class FileType(TableBase):
    __tablename__ = "file_types"

    type: Mapped[str] = mapped_column(String, primary_key=True)


class File(TableBase):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("file_types.type"))


class FileAncestorFileDescendant(TableBase):
    __tablename__ = "file_ancestors_file_descendants"

    ancestor_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"), primary_key=True)
    descendant_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id"), primary_key=True
    )
    descendant_path: Mapped[str]
    descendant_depth: Mapped[int]