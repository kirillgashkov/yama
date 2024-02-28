from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from yama.security.utils import get_user_id_from_access_token, is_access_token_valid

get_oauth2_token = OAuth2PasswordBearer(tokenUrl="/security/tokens")
get_oauth2_token_or_none = OAuth2PasswordBearer(
    tokenUrl="/security/tokens", auto_error=False
)


def get_current_user_id(token: Annotated[str, Depends(get_oauth2_token)]) -> UUID:
    if not is_access_token_valid(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    return get_user_id_from_access_token(token)


def get_current_user_id_or_none(
    token: Annotated[str | None, Depends(get_oauth2_token_or_none)],
) -> UUID | None:
    if token is None or not is_access_token_valid(token):
        return None

    return get_user_id_from_access_token(token)
