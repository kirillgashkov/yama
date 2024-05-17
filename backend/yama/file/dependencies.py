from fastapi import Request

from ._config import Config


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.file_settings  # type: ignore[no-any-return]
