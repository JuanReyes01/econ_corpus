"""What a set of cleaned tables was built from, and what it holds, written next to them.

Input: the reasons file and the review folder that `processed` used, and the tables it wrote.
Output: `manifest.json` in the folder of the cleaned tables, and a check that refuses tables
built from other reasons, other review files or other rules than the ones at hand, or tables
that are not the ones the build wrote.

Lives here: the fingerprints of the inputs, the sizes of the tables and their comparison. Does
not live here: the tables (processed) or what the later steps do with them (review_cases,
datasheet_clean, check).
"""

import json
from pathlib import Path

import pyarrow.parquet as pq

from econ_corpus import reasons, review

FILE = "manifest.json"


def current(clean: Path, reasons_file: Path, review_dir: Path | None) -> dict[str, str]:
    """Return the fingerprints of the inputs and the sizes of the tables as they are now."""
    stamps = pq.read_schema(reasons_file).metadata or {}
    parts = review.load_parts(review_dir / review.PARTS_FILE) if review_dir else {}
    pairs = review.load_pairs(review_dir / review.PAIRS_FILE) if review_dir else {}
    inputs = {
        "records": stamps.get(reasons.RECORDS_STAMP.encode(), b"").decode(),
        "rules": reasons.rules_fingerprint(),
        "reasons": reasons.fingerprint(pq.read_table(reasons_file)),
        "byline_parts": review.fingerprint(parts),
        "author_pairs": review.fingerprint(pairs),
    }
    sizes = {table.name: str(table.stat().st_size) for table in sorted(clean.glob("*.csv"))}
    return inputs | sizes


def clear(clean: Path) -> None:
    """Remove the manifest, so tables that are being rewritten cannot pass for finished."""
    (clean / FILE).unlink(missing_ok=True)


def write(clean: Path, reasons_file: Path, review_dir: Path | None) -> None:
    """Record next to the cleaned tables what they were built from and how large they are."""
    found = current(clean, reasons_file, review_dir)
    (clean / FILE).write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")


def check(clean: Path, reasons_file: Path, review_dir: Path | None) -> None:
    """Refuse cleaned tables that are not the ones built from these inputs.

    A step that reads the tables together with the reasons or the review would otherwise mix
    two states of the pipeline: after a review round or a change of the rules that was not
    followed by a new build, or after a build that was interrupted.
    """
    path = clean / FILE
    built = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    now = current(clean, reasons_file, review_dir)
    changed = sorted(name for name in now | built if now.get(name) != built.get(name))
    if changed:
        msg = (
            f"the cleaned tables in {clean} are not the ones built from these inputs "
            f"({', '.join(changed)} differ): run processed again"
        )
        raise ValueError(msg)
