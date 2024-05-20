from yama import function

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
        function_config: function.Config,
    ) -> StartedProcess: ...

    async def wait(self, process: StartedProcess, /) -> StoppedProcess: ...
