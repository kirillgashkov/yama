import asyncio
import pathlib

import aiofiles

from yama.function.driver import helper

from ._config import Config
from ._service_driver import (
    Driver,
    InputFile,
    OutputFile,
    StartedProcess,
    StoppedProcess,
)


class DockerDriver(Driver):
    async def execute(
        self,
        command: list[str],
        /,
        *,
        input_files: list[InputFile],
        output_files: list[OutputFile],
        config: Config,
    ) -> StartedProcess:
        async with aiofiles.tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = pathlib.Path(temp_dir_str)

            process = await asyncio.create_subprocess_exec(
                *config.helper_executable,
                *_make_helper_output_options(output_files=output_files),
                "--",
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir,
            )
            # TODO: Return here, maybe consider returning the task though

            # TODO: --- From here... ---
            helper_stdin = await _make_helper_stdin(input_files=input_files)

            helper_stdout, _helper_stderr = await process.communicate(
                input=helper_stdin
            )  # TODO: Log _helper_stderr
            helper_exit_code = await process.wait()
            assert helper_exit_code == 0

            path_to_content = _parse_helper_stdout(helper_stdout)
            for of in output_files:
                assert of.path in path_to_content
            for of in output_files:
                await of.content_writer.write(path_to_content[of.path])
            # TODO: --- ...to here should be an async task ---

    async def wait(self, process: StartedProcess, /) -> StoppedProcess: ...


async def _make_helper_stdin(*, input_files: list[InputFile]) -> bytes:
    files = [
        helper.FileInout(path=f.path, content=await f.content_reader.read())
        for f in input_files
    ]
    helper_in = helper.HelperIn(files=files, stdin=b"")
    helper_in_json = helper_in.model_dump_json()
    return helper_in_json.encode()


def _make_helper_output_options(*, output_files: list[OutputFile]) -> list[str]:
    options = []
    for f in output_files:
        options.append("--output")
        options.append(str(f.path))
    return options


def _parse_helper_stdout(stdout: bytes, /) -> dict[pathlib.Path, bytes]:
    helper_out = helper.HelperOut.model_validate_json(stdout)
    return {f.path: f.content for f in helper_out.files}
