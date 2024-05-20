import asyncio
import pathlib
import sys
import typing

import typer

from ._service import HelperIn, _execute

_app = typer.Typer()


@_app.command()
def _handle(
    *,
    command: list[str],
    output: typing.Annotated[list[pathlib.Path], typer.Option(default_factory=list)],
) -> None:
    async def f() -> None:
        function_in = HelperIn.model_validate_json(sys.stdin.read())
        function_out = await _execute(
            command, helper_in=function_in, output_files=output
        )
        sys.stdout.write(function_out.model_dump_json())

    asyncio.run(f())


if __name__ == "__main__":
    _app()
