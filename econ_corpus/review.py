"""Decisions taken in the manual review of doubtful authors, read from files.

Input: two CSV files kept next to the data, never in the repository, because they hold the
names of private persons (readers who signed letters):
`byline_parts.csv` (part, replacement, reason) corrects how one part of a byline is read, and
`author_pairs.csv` (key_a, key_b, decision, reason) says whether two name keys are one person.
Output: the same decisions as dictionaries, ready for `authors` and `identity`.

Lives here: reading the files. Does not live here: the review itself (done by reading each
case, see docs/decisions.md) or what a decision changes (authors, identity, processed).
"""

import csv
from pathlib import Path

PARTS_FILE, PAIRS_FILE = "byline_parts.csv", "author_pairs.csv"
NOT_A_CORRECTION = {"KEEP", "UNSURE", ""}  # the part stays as the rules read it


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_parts(path: Path) -> dict[str, str]:
    """Return part -> corrected byline; an empty byline means the part names nobody."""
    corrections = {}
    for row in _rows(path):
        replacement = row["replacement"].strip()
        if replacement not in NOT_A_CORRECTION:
            corrections[row["part"]] = "" if replacement == "NOBODY" else replacement
    return corrections


def load_pairs(path: Path) -> dict[tuple[str, str], str]:
    """Return (name key, name key) in sorted order -> 'same', 'different' or 'unsure'."""
    return {
        tuple(sorted((row["key_a"], row["key_b"]))): row["decision"].strip() for row in _rows(path)
    }
