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

from econ_corpus import authors

PARTS_FILE, PAIRS_FILE = "byline_parts.csv", "author_pairs.csv"
AS_READ = {"keep", "unsure", ""}  # the part stays as the rules read it
NOBODY = "nobody"
VERDICTS = {"same", "different", "unsure"}


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def decided_parts(path: Path) -> set[str]:
    """Return every part the review has looked at, whatever was decided."""
    return {row["part"] for row in _rows(path)}


def load_parts(path: Path) -> dict[str, str]:
    """Return part -> corrected byline; an empty byline means the part names nobody.

    A replacement must be KEEP, UNSURE, NOBODY (in any case) or a byline every part of which
    reads as a name; anything else is refused, because it would silently remove the author.
    """
    corrections = {}
    for row in _rows(path):
        replacement = row["replacement"].strip()
        if replacement.casefold() in AS_READ:
            continue
        pieces = authors.split_authors(replacement)
        if replacement.casefold() == NOBODY:
            replacement = ""
        elif not pieces or not all(authors.parse_name(piece) for piece in pieces):
            msg = f"{path.name}: {replacement!r} is not a readable byline for {row['part']!r}"
            raise ValueError(msg)
        corrections[row["part"]] = replacement
    return corrections


def load_pairs(path: Path) -> dict[tuple[str, str], str]:
    """Return (name key, name key) in sorted order -> 'same', 'different' or 'unsure'."""
    decisions = {}
    for row in _rows(path):
        verdict = row["decision"].strip().casefold()
        if verdict not in VERDICTS:
            msg = f"{path.name}: unknown decision {row['decision']!r} for {row['key_a']}"
            raise ValueError(msg)
        decisions[tuple(sorted((row["key_a"], row["key_b"])))] = verdict
    return decisions
