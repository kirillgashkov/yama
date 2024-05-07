from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase


class RevokedRefreshTokenDb(TableBase):
    __tablename__ = "revoked_refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime]
