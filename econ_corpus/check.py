"""Step 7 of the pipeline: check that the outputs on disk belong to one state, before delivery.

Input: the records, the reasons, the review folder, the raw CSV, the cleaned tables, the two
datasheet templates and the two datasheets.
Output: the list of outputs that are stale, empty when everything belongs together.

Lives here: running the guards of the other steps in one place, and building again both
datasheets with their tables and figures and the lists of review cases, to compare them with
the ones on disk. Does not live here: the guards themselves
(reasons, manifest, export) or the copying (the Makefile).

The delivery folder is copied from the working outputs, so this check is what ties one
delivery to one state of the pipeline: the reasons follow from the records and the rules,
the raw CSV and the cleaned tables from the reasons, and the datasheets from all of them.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import tempfile

from econ_corpus.clean import datasheet_clean, manifest, review_cases
from econ_corpus.names import review
from econ_corpus.raw import datasheet, exclusions, export, reasons
from econ_corpus.shared import tables


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
    tables: Path
    figures: Path
    raw_reasons: Path


def stale(paths: Paths) -> list[str]:
    """Return what is wrong with the outputs, one line each; nothing when they belong together."""
    try:
        codes = reasons.load(paths.records, paths.reasons)
        manifest.check(paths.clean, paths.records, paths.reasons, paths.review)
    except ValueError as error:
        return [str(error)]  # nothing after this can be compared
    problems = []
    if not export.is_current(paths.records, paths.reasons, paths.raw_csv):
        problems.append(f"{paths.raw_csv.name} was not made from these reasons: run export again")
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        raw, clean = work / paths.raw_md.name, work / paths.clean_md.name
        side = {"tables_dir": work / "tables", "figures_dir": work / "figures"}
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
        # The case lists are built from a copy of the review files, never into the folder.
        (work / "review").mkdir()
        for name in (review.PARTS_FILE, review.PAIRS_FILE):
            if (paths.review / name).exists():
                shutil.copy(paths.review / name, work / "review" / name)
        review_cases.build(paths.records, paths.reasons, paths.clean, work / "review")
        # The two files that step 2 writes for the delivery of the raw table.
        counts = exclusions.reason_counts(codes.to_pylist())
        tables.write_csv(counts, work / "tables" / "exclusion_counts.csv")
        export.write_reasons(paths.records, paths.reasons, work / paths.raw_reasons.name)
        built = [(raw, paths.raw_md), (clean, paths.clean_md)]
        built.append((work / paths.raw_reasons.name, paths.raw_reasons))
        for folder, on_disk in (
            (work / "tables", paths.tables),
            (work / "figures", paths.figures),
            (work / "review" / "cases", paths.review / "cases"),
        ):
            names = sorted(file.name for file in folder.glob("*"))
            built += [(folder / name, on_disk / name) for name in names]
            kept = {f.name for f in on_disk.glob("*") if f.is_file() and f.name[0] != "."}
            problems += [
                f"{name} is written by no step any more: remove it"
                for name in sorted(kept - set(names))
            ]
        for new, old in built:
            if not old.exists() or new.read_bytes() != old.read_bytes():
                problems.append(f"{old.name} is not what the data gives now: build it again")
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
            tables=Path("reports/tables"),
            figures=Path("reports/figures"),
            raw_reasons=Path("data/processed/econ_corpus_raw_reasons.csv"),
        )
    )
    if problems:
        sys.exit("stale outputs:\n- " + "\n- ".join(problems))
    print("every output belongs to the current records, reasons and review")  # noqa: T201


if __name__ == "__main__":
    main()
