from fastapi import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

INVALID_TOKEN_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
)


class InvalidTokenError(Exception): ...
