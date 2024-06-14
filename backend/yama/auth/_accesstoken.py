from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

from ._config import Config
from ._token import _InvalidTokenError


def _make_access_token_and_expires_in(
    user_id: UUID,
    /,
    *,
    settings: Config,
) -> tuple[str, int]:
    now = datetime.now(UTC)
    expire_seconds = settings.access_token.expire_seconds

    claims = {
        "sub": str(user_id),
        "exp": now + timedelta(seconds=expire_seconds),
        "iat": now,
    }

    token = jwt.encode(
        claims,
        key=settings.access_token.key,
        algorithm=settings.access_token.algorithm,
    )
    return token, expire_seconds


def _get_user_id_from_access_token(token: str, /, *, settings: Config) -> UUID:
    try:
        claims = jwt.decode(
            token,
            key=settings.access_token.key,
            algorithms=[settings.access_token.algorithm],
        )
    except JWTError:
        raise _InvalidTokenError()

    return UUID(claims["sub"])
