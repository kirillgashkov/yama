import asyncio
import sys

from typer import Typer

from ._service import HelperIn, execute

_app = Typer()


@_app.command()
def _handle(*, command: list[str]) -> None:
    async def f() -> None:
        function_in = HelperIn.model_validate_json(sys.stdin.read())
        function_out = await execute(command, helper_in=function_in)
        sys.stdout.write(function_out.model_dump_json())

    asyncio.run(f())


if __name__ == "__main__":
    _app()
