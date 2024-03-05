from enum import Enum
from uuid import UUID

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.model.models import ModelBase


class FileTypeEnum(str, Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"


class FileType(TableBase):
    __tablename__ = "file_types"

    type: Mapped[FileTypeEnum] = mapped_column(String, primary_key=True)


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
    depth: Mapped[int]


class FileOut(ModelBase):
    id: UUID
    type: FileTypeEnum
