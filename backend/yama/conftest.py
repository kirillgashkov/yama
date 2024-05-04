import pytest


@pytest.fixture(autouse=True)
def anyio_backend() -> str:
    return "asyncio"
