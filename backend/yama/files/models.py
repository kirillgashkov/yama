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


def check_file_name(name: str) -> str:
    assert len(name.encode()) <= MAX_FILE_NAME_LENGTH, "File name is too long"
    assert name.isprintable(), "File name contains non-printable characters"
    assert "/" not in name, "File name contains '/'"
    return name


def check_file_path(
    path_str: Any, handler: ValidatorFunctionWrapHandler
) -> PurePosixPath:
    assert isinstance(path_str, str), "File path is not a string"
    assert len(path_str.encode()) <= MAX_FILE_PATH_LENGTH, "File path is too long"

    path = handler(path_str)

    if not isinstance(path, PurePosixPath):
        raise RuntimeError("File path is not a PurePosixPath")

    if path.is_absolute():
        names = path.parts[1:]
    else:
        names = path.parts

    for name in names:
        check_file_name(name)

    return path


def normalize_file_path_root(path: PurePosixPath) -> PurePosixPath:
    # POSIX allows treating a path beginning with two slashes in an
    # implementation-defined manner which is respected by Python's pathlib by not
    # collapsing the two slashes into one. We treat such paths as absolute paths.
    if path.parts and path.parts[0] == "//":
        return PurePosixPath("/", *path.parts[1:])
    return path


FileName: TypeAlias = Annotated[str, AfterValidator(check_file_name)]
FileNameAdapter: TypeAdapter[FileName] = TypeAdapter(FileName)  # pyright: ignore [reportCallIssue, reportAssignmentType]

# TODO: Handle `..` in file path
FilePath: TypeAlias = Annotated[
    PurePosixPath,
    AfterValidator(normalize_file_path_root),
    WrapValidator(check_file_path),
]
FilePathAdapter: TypeAdapter[FilePath] = TypeAdapter(FilePath)  # pyright: ignore [reportCallIssue, reportAssignmentType]


class FileTypeEnum(str, Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"


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


class RegularFileCreateTuple(NamedTuple):
    content: UploadFile
    type: Literal[FileTypeEnum.REGULAR] = FileTypeEnum.REGULAR


class DirectoryCreateTuple(NamedTuple):
    type: Literal[FileTypeEnum.DIRECTORY] = FileTypeEnum.DIRECTORY


FileCreateTuple: TypeAlias = RegularFileCreateTuple | DirectoryCreateTuple


class RegularFileReadTuple(NamedTuple):
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


FileReadTuple: TypeAlias = RegularFileReadTuple | DirectoryReadTuple


class RegularFileUpdateTuple(NamedTuple):
    type: Literal[FileTypeEnum.REGULAR] = FileTypeEnum.REGULAR
    content: UploadFile | None = None


class DirectoryUpdateTuple(NamedTuple):
    type: Literal[FileTypeEnum.DIRECTORY] = FileTypeEnum.DIRECTORY


FileUpdateTuple: TypeAlias = RegularFileUpdateTuple | DirectoryUpdateTuple


class FileType(TableBase):
    __tablename__ = "file_types"

    type: Mapped[FileTypeEnum] = mapped_column(String, primary_key=True)


class File(TableBase):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[FileTypeEnum] = mapped_column(ForeignKey("file_types.type"))


class FileAncestorFileDescendant(TableBase):
    __tablename__ = "file_ancestors_file_descendants"

    ancestor_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"), primary_key=True)
    descendant_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id"), primary_key=True
    )
    descendant_path: Mapped[str]
    descendant_depth: Mapped[int]
