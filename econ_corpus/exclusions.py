"""Step 2 of the pipeline: give every row of the parsed table exactly one reason.

Input: the parquet written by `parse` (rows, footers included).
Output: a small parquet with `source_file`, `record_index` and `reason`, one row per input
row, so the counts per reason add up to the size of the raw table.

Lives here: the rules that assign a reason. Does not live here: the reasons table and its
file (reasons), the rows themselves (the parsed table is never modified) or the descriptions
of the data (datasheet).

Rules are applied in the order of REASONS; the first one that matches decides. Only
obvious cases are handled: repeated ProQuest ids, publications that were not queried,
identical text with the same title, date and newspaper, and records in a news section with no
sign of being opinion. A record that cannot be decided (no section, generic type, no opinion
title) is `unclear_opinion`: it stays in the raw table and is left out of the cleaned dataset.
An opinion piece then needs text and a person among its authors. Subtler duplicates come later.

Two flags per reason: `in_raw` says whether the row is part of the shared raw table (footers,
repeated ids and repeated text are not), `dropped` whether it leaves the cleaned dataset.
"""

from collections.abc import Iterable
from pathlib import Path

import pyarrow.parquet as pq

from econ_corpus import bylines, datasheet, parse, review, summaries
from econ_corpus.reasons import INPUTS, REASONS, write_reasons
from econ_corpus.tables import Articles, Table

# A body shorter than PLACEHOLDER_WORDS carried by PLACEHOLDER_ARTICLES or more different
# articles is a notice ("text not available") or a credit, not the text of those articles.
PLACEHOLDER_WORDS, PLACEHOLDER_ARTICLES = 100, 5


def _opinion_reason(doc_type: str | None, section: str | None, title: str | None) -> str:
    """Return the reason for a record that is not a duplicate.

    An opinion title, document type or section keeps the record. Without any of them, a record
    with no section is unclear (the section is what would settle it), and one in a news
    section is not opinion.
    """
    labels = summaries.split_labels(doc_type)
    if summaries.is_opinion_title(title):
        return "kept"
    if not labels and section is None:
        return "missing_metadata"
    if any(map(summaries.is_opinion_label, labels)) or summaries.is_opinion_section(section):
        return "kept"
    return "unclear_opinion" if section is None else "not_opinion"


def _author_reason(byline: str | None, corrections: dict[str, str] | None) -> str:
    """Return the reason for an opinion piece with text, given its byline."""
    if not bylines.is_signed(byline):
        return "no_author"
    return "kept" if bylines.people(byline, corrections) else "no_person_author"


def _kept_copies(rows: Articles, order: list[int]) -> dict[int, int]:
    """Return, for each ProQuest id, the row to keep: the longest body, then the earliest download.

    A later copy can be the only one with text (some downloads came out without body), so
    the earliest copy alone is not a safe choice.
    """
    kept: dict[int, int] = {}
    for i in order:
        doc_id = rows["doc_id"][i]
        if rows["is_footer"][i] or doc_id is None:
            continue
        # Strictly longer, so on a tie the earliest copy stays.
        if doc_id not in kept or (rows["body_chars"][i] or 0) > (
            rows["body_chars"][kept[doc_id]] or 0
        ):
            kept[doc_id] = i
    return kept


def _mark_repeated_text(
    groups: Iterable[list[int]], reasons: list[str], qualifies: set[int]
) -> None:
    """Leave one copy of each repeated text and mark the others `duplicate_text`, in place."""
    for copies in groups:
        stays = next((i for i in copies if i in qualifies), copies[0])
        for i in copies:
            if i != stays:
                reasons[i] = "duplicate_text"


def _before_judging(rows: Articles, i: int, kept: dict[int, int], family: str | None) -> str:
    """Return the reason of a row that is not judged on its content, or '' if it is."""
    doc_id = rows["doc_id"][i]
    if rows["is_footer"][i]:
        return "file_footer"
    if doc_id is not None and kept[doc_id] != i:
        return "duplicate_id"
    if family == "Other":
        return "not_queried_newspaper"
    # Without a publication the newspaper cannot be checked; without an id there is no key.
    return "missing_metadata" if family is None or doc_id is None else ""


def _placeholders(rows: Articles, judged: list[int]) -> set[str]:
    """Return the bodies that are a notice shared by different articles, not their text.

    Articles are counted, not rows: an article is a title on a date, so the copies of one
    article share a body without making it a notice. A long body under several titles is
    real text printed more than once.
    """
    articles: dict[str, set[tuple]] = {}
    for i in judged:
        if (rows["body_words"][i] or 0) < PLACEHOLDER_WORDS:
            article = (parse.compact(rows["title"][i] or ""), rows["pub_date"][i])
            articles.setdefault(rows["body_sha256"][i], set()).add(article)
    return {sha for sha, found in articles.items() if len(found) >= PLACEHOLDER_ARTICLES}


def assign_reasons(rows: Articles, corrections: dict[str, str] | None = None) -> list[str]:
    """Return one reason code per row, with repeats judged in download order.

    Of the copies of a ProQuest id, only the one chosen by `_kept_copies` is judged on its
    merits; the others are `duplicate_id`. Of the copies of a text under several ids, the one
    that stays is the earliest signed opinion piece with text, or the earliest of all if there
    is none; the others are `duplicate_text`. So each article is counted once and a signed copy
    is not lost to an unsigned one. "Signed" means any byline other than Anonymous: the choice
    must not depend on how names are read or on the manual review, because these rows also
    leave the shared raw table. A short body carried by many different articles is a placeholder
    ("text not available"), not text (see `_placeholders`).
    """
    n = len(rows["source_file"])
    file_key = {f: summaries.file_order(f) for f in set(rows["source_file"])}
    order = sorted(
        range(n), key=lambda i: (file_key[rows["source_file"][i]], rows["record_index"][i])
    )
    kept = _kept_copies(rows, order)
    families = [summaries.newspaper_family(key) for key in rows["publication_key"]]
    reasons = [_before_judging(rows, i, kept, families[i]) for i in range(n)]
    judged = [i for i in order if not reasons[i]]
    placeholders = _placeholders(rows, judged)
    same_text: dict[tuple, list[int]] = {}  # copies of one text, in download order
    by_byline: dict[str | None, str] = {}  # bylines repeat, so each is read once
    qualifies: set[int] = set()  # signed opinion pieces with text
    for i in judged:
        title, sha = rows["title"][i], rows["body_sha256"][i]
        reasons[i] = _opinion_reason(rows["doc_type"][i], rows["section"][i], title)
        if sha and title and rows["pub_date"][i]:
            # Titles are compared without ProQuest's stray spaces, like every other metadata.
            text_key = (sha, parse.compact(title), rows["pub_date"][i], families[i])
            same_text.setdefault(text_key, []).append(i)
        if reasons[i] == "kept":
            # An opinion piece stays only with text and with a person among its authors.
            byline = rows["author"][i]
            if byline not in by_byline:
                by_byline[byline] = _author_reason(byline, corrections)
            has_text = rows["body_chars"][i] and sha not in placeholders
            reasons[i] = by_byline[byline] if has_text else "no_text"
            if reasons[i] not in ("no_text", "no_author"):
                qualifies.add(i)
    _mark_repeated_text(same_text.values(), reasons, qualifies)
    return reasons


def reason_counts(reasons: list[str]) -> Table:
    """Count rows per reason, in table order, with a total row that must equal the input."""
    total = len(reasons)
    counts = {r["code"]: 0 for r in REASONS}
    for reason in reasons:
        counts[reason] += 1
    body = [
        [
            r["code"],
            r["description"],
            summaries.num(counts[r["code"]]),
            summaries.pct(counts[r["code"]], total),
            "yes" if r["in_raw"] else "no",
            "yes" if r["dropped"] else "no",
        ]
        for r in REASONS
    ]
    header = ["Reason", "Meaning", "Records", "Share", "In raw", "Dropped"]
    total_row = ["Total", "", summaries.num(total), summaries.pct(total, total), "", ""]
    return [header, *body, total_row]


def write_exclusions(
    parquet: Path, out: Path, corrections: dict[str, str] | None = None
) -> list[str]:
    """Assign a reason to every row of the parsed table and write them next to their keys."""
    table = pq.read_table(parquet, columns=INPUTS)
    reasons = assign_reasons(table.to_pydict(), corrections)
    # The reasons depend on the review, so they carry its fingerprint (see review.same_review).
    write_reasons(table, reasons, out, {review.STAMP: review.fingerprint(corrections or {})})
    return reasons


def main() -> None:
    """Assign reasons to the parsed table at its default location and save the counts."""
    reasons = write_exclusions(
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        review.load_parts(review.folder(Path("data/review")) / review.PARTS_FILE),
    )
    datasheet.write_csv(reason_counts(reasons), Path("reports/tables/exclusion_counts.csv"))


if __name__ == "__main__":
    main()
