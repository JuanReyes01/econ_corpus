"""Pipeline 2, in order: from the records and their reasons to the cleaned dataset.

    uv run python -m econ_corpus.clean

Input: what pipeline 1 wrote (`records.parquet`, `exclusions.parquet`) and the review files.
Output: everything listed in README.md of this folder, step by step.

Lives here: the order of the steps. Does not live here: what each step does (its module).
"""

from econ_corpus import overview
from econ_corpus.clean import datasheet_clean, processed, review_cases

STEPS = {
    "processed": processed.main,  # step 4: the cleaned tables
    "review_cases": review_cases.main,  # step 5: the cases left for the manual review
    "datasheet_clean": datasheet_clean.main,  # step 6: the datasheet of the cleaned dataset
    "overview": overview.main,  # step 6b: the overview of both pipelines
}


def main() -> None:
    """Run the steps in order; a step that fails stops the ones after it."""
    for number, name in enumerate(STEPS, start=1):
        print(f"[clean {number}/{len(STEPS)}] {name}", flush=True)  # noqa: T201
        STEPS[name]()


if __name__ == "__main__":
    main()
