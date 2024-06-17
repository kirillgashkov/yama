import base64
import logging
import pathlib
import subprocess
import sys
from typing import Annotated

import pydantic
import typer

logger = logging.getLogger(__name__)

cli = typer.Typer()


class FileInout(pydantic.BaseModel):
    path: pathlib.Path
    content: pydantic.Base64Bytes


class HelperIn(pydantic.BaseModel):
    files: list[FileInout] = pydantic.Field(default_factory=list)
    stdin: pydantic.Base64Bytes = b""


class HelperOut(pydantic.BaseModel):
    files: list[FileInout]
    stdout: pydantic.Base64Bytes
    stderr: pydantic.Base64Bytes
    exit_code: int


@cli.command()
def handle(
    *,
    command: list[str],
    output_file_paths: Annotated[
        list[pathlib.Path], typer.Option("--output", "-o", default_factory=list)
    ],
) -> None:
    """
    Writes input files received via stdin, executes command, reads output files and
    sends them to stdout.
    """
    helper_in = HelperIn.model_validate_json(sys.stdin.read())
    _write_input_files(helper_in.files)

    p = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(helper_in.stdin)
    exit_code = p.returncode
    assert isinstance(exit_code, int)

    files = _read_output_files(output_file_paths)
    helper_out = HelperOut(
        files=files,
        stdout=base64.encodebytes(stdout),
        stderr=base64.encodebytes(stderr),
        exit_code=exit_code,
    )
    sys.stdout.write(helper_out.model_dump_json())


def _write_input_files(files: list[FileInout], /) -> None:
    for f in files:
        f.path.parent.mkdir(parents=True, exist_ok=True)
        with open(f.path, "wb") as w:
            w.write(f.content)


def _read_output_files(output_file_paths: list[pathlib.Path], /) -> list[FileInout]:
    files: list[FileInout] = []

    for fp in output_file_paths:
        if not fp.exists():
            logger.warning("Output file '%s' does not exist", fp)
            c = b""
        elif not fp.is_file():
            logger.warning("Output file '%s' is not a regular file", fp)
            c = b""
        else:
            with open(fp, "rb") as r:
                c = r.read()

        files.append(FileInout(path=fp, content=base64.encodebytes(c)))

    return files
