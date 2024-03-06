from pathlib import Path


def export_pdf(
    path: Path,
    /,
    *,
    auxiliary_dir: Path,
    pandoc_executable: Path,
    pandoc_reader: Path,
    pandoc_writer: Path,
    pandoc_template: Path,
    pandoc_variables: dict[str, str],
    latexmk_executable: Path,
) -> Path:
    ...
