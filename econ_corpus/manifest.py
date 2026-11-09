"""What a set of cleaned tables was built from, written next to them.

Input: the reasons file and the review folder that `processed` used.
Output: `manifest.json` in the folder of the cleaned tables, and a check that refuses tables
built from other reasons or other review files than the ones at hand.

Lives here: the fingerprints of the inputs and their comparison. Does not live here: the
tables (processed) or what the later steps do with them (review_cases, datasheet_clean).
"""

import json
from pathlib import Path

import pyarrow.parquet as pq

from econ_corpus import reasons, review

FILE = "manifest.json"


def current(reasons_file: Path, review_dir: Path | None) -> dict[str, str]:
    """Return the fingerprints of the reasons and of the review files as they are now."""
    stamps = pq.read_schema(reasons_file).metadata or {}
    parts = review.load_parts(review_dir / review.PARTS_FILE) if review_dir else {}
    pairs = review.load_pairs(review_dir / review.PAIRS_FILE) if review_dir else {}
    return {
        "records": stamps.get(reasons.RECORDS_STAMP.encode(), b"").decode(),
        "reasons": reasons.fingerprint(pq.read_table(reasons_file)),
        "byline_parts": review.fingerprint(parts),
        "author_pairs": review.fingerprint(pairs),
    }


def write(clean: Path, reasons_file: Path, review_dir: Path | None) -> None:
    """Record next to the cleaned tables what they were built from."""
    found = current(reasons_file, review_dir)
    (clean / FILE).write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")


def check(clean: Path, reasons_file: Path, review_dir: Path | None) -> None:
    """Refuse cleaned tables built from other reasons or review files than these.

    A step that reads the tables together with the reasons or the review would otherwise mix
    two states of the pipeline, for example after a review round that was not followed by a
    new build.
    """
    path = clean / FILE
    built = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    changed = [
        name for name, code in current(reasons_file, review_dir).items() if built.get(name) != code
    ]
    if changed:
        msg = (
            f"the cleaned tables in {clean} were built from other inputs "
            f"({', '.join(changed)} changed): run processed again"
        )
        raise ValueError(msg)
