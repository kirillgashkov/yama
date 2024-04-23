from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.model.models import ModelBase


class User(TableBase):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    username: Mapped[str]
    password_hash: Mapped[str]


class UserIn(ModelBase):
    username: str
    password: str


class UserOut(ModelBase):
    id: UUID
    username: str
