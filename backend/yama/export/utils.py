import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


# FIXME: Add security
def export_pdf(
    file: Path,
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
    tex_file = auxiliary_dir / file.with_suffix(".tex").name
    pdf_dir = auxiliary_dir / "pdf"
    pdf_file = pdf_dir / tex_file.with_suffix(".pdf").name
    pandoc_out = auxiliary_dir / "pandoc.out"
    pandoc_err = auxiliary_dir / "pandoc.err"
    latexmk_out = auxiliary_dir / "latexmk.out"
    latexmk_err = auxiliary_dir / "latexmk.err"

    auxiliary_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Converting %s to %s", file, tex_file)
    with open(pandoc_out, "w") as out, open(pandoc_err, "w") as err:
        subprocess.run(
            [
                str(pandoc_executable),
                "--from",
                str(pandoc_reader),
                "--to",
                str(pandoc_writer),
                "--standalone",
                "--template",
                str(pandoc_template),
                *[
                    f"--variable={key}={value}"
                    for key, value in pandoc_variables.items()
                ],
                "--output",
                str(tex_file),
                str(file),
            ],
            stdout=out,
            stderr=err,
            check=True,
        )

    logger.info("Compiling %s to %s", tex_file, pdf_file)
    with open(latexmk_out, "w") as out, open(latexmk_err, "w") as err:
        subprocess.run(
            [
                str(latexmk_executable),
                "-xelatex",
                "-bibtex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                "-shell-escape",  # Needed for `minted`, has security implications
                "-output-directory=" + str(pdf_dir),
                str(tex_file),
            ],
            stdout=out,
            stderr=err,
            check=True,
        )

    return pdf_file
