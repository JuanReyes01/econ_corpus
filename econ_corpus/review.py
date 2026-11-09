"""Decisions taken in the manual review of doubtful authors, read from files.

Input: two CSV files kept next to the data, never in the repository, because they hold the
names of private persons (readers who signed letters):
`byline_parts.csv` (part, replacement, reason) corrects how one part of a byline is read, and
`author_pairs.csv` (key_a, key_b, decision, reason) says whether two name keys are one person.
Output: the same decisions as dictionaries, ready for `authors` and `identity`.

Lives here: reading the files. Does not live here: the review itself (done by reading each
case, see docs/decisions.md) or what a decision changes (authors, identity, processed).
"""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from econ_corpus import authors

PARTS_FILE, PAIRS_FILE = "byline_parts.csv", "author_pairs.csv"
STAMP = "byline_parts"  # metadata key of the reasons file that holds the fingerprint
AS_READ = {"keep", "unsure", ""}  # the part stays as the rules read it
NOBODY = "nobody"
CAUTION = {"same": 0, "unsure": 1, "different": 2}  # of two verdicts, the higher stays
VERDICTS = set(CAUTION)
Decisions = dict[tuple[str, str], str]


def folder(path: Path) -> Path:
    """Return the folder of the review files, refusing one that does not exist.

    The review files are not in the repository, so a missing folder is a copy of the project
    without them, not a review with no decisions: running on would silently undo the review.
    An empty folder is the way to say that there is no review.
    """
    if not path.is_dir():
        msg = (
            f"the review folder {path} does not exist: restore the review files into it "
            "(README.md says where they are kept) or create it empty to run with no review"
        )
        raise FileNotFoundError(msg)
    return path


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _refuse_repeats(path: Path, items: list) -> None:
    """Refuse a review file that decides the same case twice: it would have no single answer."""
    seen = set()
    for item in items:
        if item in seen:
            msg = f"{path.name}: {item!r} is listed twice"
            raise ValueError(msg)
        seen.add(item)


def decided_parts(path: Path) -> set[str]:
    """Return every part the review has looked at, whatever was decided."""
    return {row["part"] for row in _rows(path)}


def load_parts(path: Path) -> dict[str, str]:
    """Return part -> corrected byline; an empty byline means the part names nobody.

    A replacement must be KEEP, UNSURE, NOBODY (in any case) or names written 'Family, Given'
    and separated by ';'; anything else is refused, because it would silently remove the author.
    """
    rows = _rows(path)
    _refuse_repeats(path, [row["part"] for row in rows])
    corrections = {}
    for row in rows:
        replacement = row["replacement"].strip()
        if replacement.casefold() in AS_READ:
            continue
        pieces = [authors.reviewed_name(piece) for piece in replacement.split(";")]
        if replacement.casefold() == NOBODY:
            replacement = ""
        elif not all(pieces):
            msg = f"{path.name}: {replacement!r} is not a readable byline for {row['part']!r}"
            raise ValueError(msg)
        corrections[row["part"]] = replacement
    return corrections


def load_pairs(path: Path) -> Decisions:
    """Return (name key, name key) in sorted order -> 'same', 'different' or 'unsure'."""
    rows = _rows(path)
    pairs = [tuple(sorted((row["key_a"], row["key_b"]))) for row in rows]
    _refuse_repeats(path, pairs)
    decisions = {}
    for pair, row in zip(pairs, rows, strict=True):
        verdict = row["decision"].strip().casefold()
        if verdict not in VERDICTS:
            msg = f"{path.name}: unknown decision {row['decision']!r} for {row['key_a']}"
            raise ValueError(msg)
        decisions[pair] = verdict
    return decisions


def verdicts(decisions: Decisions, resolved: dict[str, str]) -> Decisions:
    """Return the verdict on each pair of authors that the review left apart.

    `resolved` maps a name key to the key of its author. A pair judged different that ends up
    as one author (through a chain of 'same' verdicts) contradicts the review, so it is
    refused rather than hidden. A pair the review was unsure about may be merged by the rule.
    Of two verdicts on one pair of authors, the more cautious stays.
    """
    found: Decisions = {}
    for (a, b), verdict in decisions.items():
        if a not in resolved or b not in resolved:
            continue
        pair = tuple(sorted((resolved[a], resolved[b])))
        if pair[0] == pair[1] and verdict == "different":
            msg = f"{a} and {b} were judged {verdict} but are one author: check the review files"
            raise ValueError(msg)
        if pair[0] != pair[1] and CAUTION[verdict] > CAUTION[found.get(pair, "same")]:
            found[pair] = verdict
    return found


def outcome_counts(parts: list[dict[str, str]], pairs: list[dict[str, str]]) -> dict[str, int]:
    """Count the decisions of the review files, given their rows as read from disk."""
    marks = Counter(row["replacement"].strip().casefold() for row in parts)
    verdicts = Counter(row["decision"].strip().casefold() for row in pairs)
    return {
        "n_review_parts": len(parts),
        "n_parts_corrected": len(parts) - sum(marks[m] for m in (*AS_READ, NOBODY)),
        "n_parts_nobody": marks[NOBODY],
        "n_parts_keep": marks["keep"] + marks[""],  # an empty replacement keeps the reading
        "n_parts_unsure": marks["unsure"],
        "n_review_pairs": len(pairs),
        "n_pairs_same": verdicts["same"],
        "n_pairs_different": verdicts["different"],
        "n_pairs_unsure": verdicts["unsure"],
    }


def fingerprint(decisions: dict) -> str:
    """Return a short code that changes whenever a decision is added, removed or edited."""
    return hashlib.sha256(json.dumps(sorted(decisions.items())).encode()).hexdigest()[:16]


def same_review(reasons_file: Path, corrections: dict[str, str]) -> None:
    """Refuse a reasons file that was computed with other corrections than these.

    The corrections decide whether a byline names a person, so reasons computed before a
    review round would keep or leave out the wrong articles.
    """
    stored = pq.read_schema(reasons_file).metadata or {}
    stamp = stored.get(STAMP.encode(), fingerprint({}).encode()).decode()
    if stamp != fingerprint(corrections):
        msg = f"{reasons_file.name} was computed with other review files: run the exclusions again"
        raise ValueError(msg)
