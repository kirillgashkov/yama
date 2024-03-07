from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Any, TypeAlias
from uuid import UUID

from pydantic import AfterValidator, ValidatorFunctionWrapHandler, WrapValidator
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


FileName: TypeAlias = Annotated[str, AfterValidator(check_file_name)]
FilePath: TypeAlias = Annotated[PurePosixPath, WrapValidator(check_file_path)]


class FileTypeEnum(str, Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"


class FileIn(ModelBase):
    parent_path: FilePath
    name: FileName
    type: FileTypeEnum


class FileOut(ModelBase):
    path: FilePath
    id: UUID
    type: FileTypeEnum


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
    depth: Mapped[int]
