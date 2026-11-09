"""Step 7 of the pipeline: check that the outputs on disk belong to one state, before delivery.

Input: the records, the reasons, the review folder, the raw CSV, the cleaned tables, the two
datasheet templates and the two datasheets.
Output: the list of outputs that are stale, empty when everything belongs together.

Lives here: running the guards of the other steps in one place and building both datasheets
again to compare them with the ones on disk. Does not live here: the guards themselves
(reasons, manifest, export) or the copying (the Makefile).

The delivery folder is copied from the working outputs, so this check is what ties one
delivery to one state of the pipeline: the reasons follow from the records and the rules,
the raw CSV and the cleaned tables from the reasons, and the datasheets from all of them.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile

from econ_corpus import datasheet, datasheet_clean, export, manifest, reasons, review


@dataclass
class Paths:
    """Where the inputs and outputs of the pipeline are."""

    records: Path
    reasons: Path
    review: Path
    raw_csv: Path
    clean: Path
    raw_template: Path
    raw_md: Path
    clean_template: Path
    clean_md: Path


def stale(paths: Paths) -> list[str]:
    """Return what is wrong with the outputs, one line each; nothing when they belong together."""
    try:
        reasons.load(paths.records, paths.reasons)
        manifest.check(paths.clean, paths.reasons, paths.review)
    except ValueError as error:
        return [str(error)]  # nothing after this can be compared
    problems = []
    if not export.is_current(paths.records, paths.reasons, paths.raw_csv):
        problems.append(f"{paths.raw_csv.name} was not made from these reasons: run export again")
    with tempfile.TemporaryDirectory() as scratch:
        raw, clean = Path(scratch) / "raw.md", Path(scratch) / "clean.md"
        side = {"tables_dir": Path(scratch), "figures_dir": Path(scratch)}
        datasheet.build(paths.records, paths.reasons, paths.raw_template, raw, **side)
        datasheet_clean.build(
            paths.clean,
            paths.records,
            paths.reasons,
            paths.review,
            template=paths.clean_template,
            out_md=clean,
            **side,
        )
        for built, on_disk in ((raw, paths.raw_md), (clean, paths.clean_md)):
            if built.read_text(encoding="utf-8") != on_disk.read_text(encoding="utf-8"):
                problems.append(f"{on_disk.name} is not what the data gives now: build it again")
    return problems


def main() -> None:
    """Check the outputs at the repo's default locations; stop with the list of stale ones."""
    problems = stale(
        Paths(
            records=Path("data/interim/records.parquet"),
            reasons=Path("data/interim/exclusions.parquet"),
            review=review.folder(Path("data/review")),
            raw_csv=Path("data/processed/econ_corpus_raw.csv"),
            clean=Path("data/processed/clean"),
            raw_template=Path("docs/datasheet_raw.template.md"),
            raw_md=Path("docs/datasheet_raw.md"),
            clean_template=Path("docs/datasheet_clean.template.md"),
            clean_md=Path("docs/datasheet_clean.md"),
        )
    )
    if problems:
        sys.exit("stale outputs:\n- " + "\n- ".join(problems))
    print("every output belongs to the current records, reasons and review")  # noqa: T201


if __name__ == "__main__":
    main()
