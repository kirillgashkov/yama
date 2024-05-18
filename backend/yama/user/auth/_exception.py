from fastapi import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

INVALID_USERNAME_OR_PASSWORD_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid username or password."
)
INVALID_TOKEN_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
)


class InvalidUsernameOrPasswordError(Exception): ...


class InvalidTokenError(Exception): ...
