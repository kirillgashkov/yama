from typing import Annotated, Literal

from fastapi import Form

from yama.user.auth.models import GrantIn, GrantInAdapter


def get_grant_in(
    *,
    grant_type: Annotated[Literal["password"] | Literal["refresh_token"], Form()],
    username: Annotated[str | None, Form()] = None,
    password: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    scope: Annotated[Literal[None], Form()] = None,
) -> GrantIn:
    return GrantInAdapter.validate_python(
        {
            "grant_type": grant_type,
            "username": username,
            "password": password,
            "refresh_token": refresh_token,
            "scope": scope,
        }
    )