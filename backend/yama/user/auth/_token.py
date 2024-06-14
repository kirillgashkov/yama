from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from starlette.status import HTTP_401_UNAUTHORIZED

_INVALID_TOKEN_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
)


class _InvalidTokenError(Exception): ...


class _TokenOut(BaseModel):
    """https://datatracker.ietf.org/doc/html/rfc6749#section-5.1."""

    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    refresh_token: str | None = None
    scope: Literal[None] = None
