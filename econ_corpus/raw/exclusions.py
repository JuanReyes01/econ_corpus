"""Step 2 of the pipeline: give every row of the parsed table exactly one reason.

Input: the parquet written by `parse` (rows, footers included).
Output: a small parquet with `source_file`, `record_index` and `reason`, one row per input
row, so the counts per reason add up to the size of the raw table.

Lives here: the order in which the rules assign a reason, and the count per reason. Does
not live here: the rules judged on one record (record_rules), the copies of a record or of a
text (repeats), the reasons table and its file (reasons), the rows themselves (the parsed
table is never modified) or the descriptions of the data (datasheet).

Rules are applied in the order of REASONS; the first one that matches decides. Only
obvious cases are handled: repeated ProQuest ids, publications that were not queried,
identical text in the same newspaper, and records in a news section with no sign of being
opinion. A record that cannot be decided (no section, generic type, no opinion
title) is `unclear_opinion`: it stays in the raw table and is left out of the cleaned dataset.
An opinion piece then needs text and a person among its authors, and at least
`prose.MIN_OWN_WORDS` words written by its author, in English. Copies whose text differs
(edited versions) come later.

Two flags per reason: `in_raw` says whether the row is part of the shared raw table (footers,
repeated ids and repeated text are not), `dropped` whether it leaves the cleaned dataset.
"""

from pathlib import Path

import pyarrow.parquet as pq

from econ_corpus.names import review
from econ_corpus.raw import export, language, prose, record_rules, repeats, text_marks
from econ_corpus.raw.reasons import INPUTS, REASONS, check_parser, write_reasons
from econ_corpus.shared import summaries, tables
from econ_corpus.shared.tables import Articles, Table


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


def assign_reasons(
    rows: Articles,
    corrections: dict[str, str] | None = None,
    marks: text_marks.Marks | None = None,
) -> list[str]:
    """Return one reason code per row, with repeats judged in download order.

    Of the copies of a ProQuest id, only the one chosen by `repeats.kept_copies` is judged on
    its merits; the others are `duplicate_id`. Of the copies of a text under several ids (see
    `repeats.text_key`), one stays (see `repeats.mark_repeated_text`); the others are
    `duplicate_text`. So a text is counted once per newspaper and a signed copy is not lost to
    an unsigned one. "Signed" means any byline other than Anonymous: the choice must not
    depend on how names are read or on the manual review, because these rows also leave the
    shared raw table. A short body carried by many different articles is a placeholder ("text
    not available"), not text (see `repeats.placeholders`). A page under the heading of a
    compiled page (jokes, quotes of others, a poll on them) has no author, whoever signs it.
    A piece that passes every rule is
    still left out of the cleaned dataset as `short_or_cartoon` when `marks.own_words` gives
    it fewer than `prose.MIN_OWN_WORDS` words of its author (a drawing, a photograph, a list
    of links), and as `not_english` when `marks.english` gives its text a share of common
    English words under `language.MIN_ENGLISH`. The marks come from `text_marks.read`; a
    mark that is None skips its rule.
    """
    n = len(rows["source_file"])
    file_key = {f: summaries.file_order(f) for f in set(rows["source_file"])}
    order = sorted(
        range(n), key=lambda i: (file_key[rows["source_file"][i]], rows["record_index"][i])
    )
    kept = repeats.kept_copies(rows, order)
    families = [summaries.newspaper_family(key) for key in rows["publication_key"]]
    reasons = [_before_judging(rows, i, kept, families[i]) for i in range(n)]
    judged = [i for i in order if not reasons[i]]
    placeholders = repeats.placeholders(rows, judged)
    same_text: dict[tuple, list[int]] = {}  # copies of one text, in download order
    by_byline: dict[str | None, str] = {}  # bylines repeat, so each is read once
    qualifies: set[int] = set()  # signed opinion pieces with text, however short
    marks = marks or text_marks.Marks()
    for i in judged:
        title, sha = rows["title"][i], rows["body_sha256"][i]
        marked = marks.rubric is not None and marks.rubric[i]
        reasons[i] = record_rules.opinion_reason(
            rows["doc_type"][i], rows["section"][i], title, rubric=marked
        )
        if text_key := repeats.text_key(rows, i, families[i]):
            same_text.setdefault(text_key, []).append(i)
        if reasons[i] == "kept":
            # An opinion piece stays only with text and with a person among its authors.
            byline = rows["author"][i]
            if byline not in by_byline:
                by_byline[byline] = record_rules.author_reason(byline, corrections)
            has_text = rows["body_chars"][i] and sha not in placeholders
            reasons[i] = by_byline[byline] if has_text else "no_text"
            poll = marks.poll is not None and marks.poll[i]
            if reasons[i] == "kept" and record_rules.compiled(rows, i, families[i], poll=poll):
                reasons[i] = "no_person_author"  # whoever compiled a page is not its author
            if reasons[i] not in ("no_text", "no_author"):
                qualifies.add(i)
            # Decided last and outside `qualifies`, so the raw table does not depend on it.
            written = None if marks.own_words is None else marks.own_words[i]
            if reasons[i] == "kept" and written is not None and written < prose.MIN_OWN_WORDS:
                reasons[i] = "short_or_cartoon"
            share = None if marks.english is None else marks.english[i]
            if reasons[i] == "kept" and share is not None and share < language.MIN_ENGLISH:
                reasons[i] = "not_english"
    repeats.mark_repeated_text(same_text.values(), reasons, qualifies, rows["pub_date"])
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
    check_parser(parquet)
    table = pq.read_table(parquet, columns=INPUTS)
    marks = text_marks.read(parquet)
    reasons = assign_reasons(table.to_pydict(), corrections, marks)
    # The reasons depend on the review, so they carry its fingerprint (see review.same_review).
    write_reasons(table, reasons, out, {review.STAMP: review.fingerprint(corrections or {})})
    return reasons


def main() -> None:
    """Assign reasons to the parsed table at its default location.

    The counts per reason and the reasons of the rows of the raw table are saved too: they
    are the two files delivered next to that table.
    """
    records, out = Path("data/interim/records.parquet"), Path("data/interim/exclusions.parquet")
    corrections = review.load_parts(review.folder(Path("data/review")) / review.PARTS_FILE)
    reasons = write_exclusions(records, out, corrections)
    tables.write_csv(reason_counts(reasons), Path("reports/tables/exclusion_counts.csv"))
    export.write_reasons(records, out, Path("data/processed/econ_corpus_raw_reasons.csv"))


if __name__ == "__main__":
    main()
