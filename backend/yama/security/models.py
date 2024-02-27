from typing import Literal

from yama.model.models import ModelBase


class Token(ModelBase):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
