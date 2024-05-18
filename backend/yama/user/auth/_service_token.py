from fastapi import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

_INVALID_TOKEN_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
)


class _InvalidTokenError(Exception): ...
