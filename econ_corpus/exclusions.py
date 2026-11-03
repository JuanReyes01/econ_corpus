"""Stage 3 of the pipeline: give every row of the raw table exactly one reason.

Input: the parquet written by `parse` (rows, footers included).
Output: a small parquet with `source_file`, `record_index` and `reason`, one row per input
row, so the counts per reason add up to the size of the raw table.

Lives here: the reasons table and the rules that assign a reason. Does not live here: the
rows themselves (the raw table is never modified) or the descriptions of the data (datasheet).

Rules are applied in the order of REASONS; the first one that matches decides. Only
obvious cases are handled: publications that were not queried, repeated ProQuest ids,
identical text with the same title, date and newspaper, and records in a news section with no
sign of being opinion. A record that
cannot be decided (no section, generic type, no opinion title) is not dropped but flagged
`unclear_opinion`, to be settled by whoever uses the data. Subtler duplicates come later.
"""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from econ_corpus import datasheet, summaries
from econ_corpus.tables import Articles, Table

# The reasons table: code and meaning, in the order the rules are applied.
REASONS = [
    {
        "code": "file_footer",
        "description": "Row is the footer of an export file, not an article",
        "dropped": True,
    },
    {
        "code": "not_queried_newspaper",
        "description": "Publication is not one of the queried newspapers",
        "dropped": True,
    },
    {
        "code": "duplicate_id",
        "description": "Repeats a ProQuest id seen in an earlier download",
        "dropped": True,
    },
    {
        "code": "duplicate_text",
        "description": "Same body, title, date and newspaper as an earlier record",
        "dropped": True,
    },
    {
        "code": "missing_metadata",
        "description": "No document type, no section and no opinion title: cannot be classified",
        "dropped": True,
    },
    {
        "code": "not_opinion",
        "description": "A news section, and neither an opinion document type nor an opinion title",
        "dropped": True,
    },
    {
        "code": "unclear_opinion",
        "description": "Generic document type, no section and no opinion title: may be opinion",
        "dropped": False,
    },
    {
        "code": "kept",
        "description": "Shows an opinion signal and passes every rule",
        "dropped": False,
    },
]
COLUMNS = [
    "is_footer", "source_file", "record_index", "doc_id", "body_sha256", "title", "pub_date",
    "publication_key", "doc_type", "section",
]  # fmt: skip


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


def assign_reasons(rows: Articles) -> list[str]:
    """Return one reason code per row, with duplicates judged in download order.

    The earliest download of a repeated article is the one that is judged on its merits; its
    later copies are duplicates, so each article is counted once.
    """
    n = len(rows["source_file"])
    file_key = {f: summaries.file_order(f) for f in set(rows["source_file"])}
    order = sorted(
        range(n), key=lambda i: (file_key[rows["source_file"][i]], rows["record_index"][i])
    )
    seen_ids: set[int] = set()
    seen_text: set[tuple] = set()
    reasons = [""] * n
    for i in order:
        doc_id, sha, title, day = (
            rows["doc_id"][i],
            rows["body_sha256"][i],
            rows["title"][i],
            rows["pub_date"][i],
        )
        text_key = (sha, title, day, summaries.newspaper_family(rows["publication_key"][i]))
        if rows["is_footer"][i]:
            reasons[i] = "file_footer"
        elif summaries.newspaper_family(rows["publication_key"][i]) == "Other":
            reasons[i] = "not_queried_newspaper"
        elif doc_id is not None and doc_id in seen_ids:
            reasons[i] = "duplicate_id"
        elif sha and title and day and text_key in seen_text:
            reasons[i] = "duplicate_text"
        else:
            reasons[i] = _opinion_reason(rows["doc_type"][i], rows["section"][i], title)
        if doc_id is not None:
            seen_ids.add(doc_id)
        if sha and title and day and not rows["is_footer"][i]:
            seen_text.add(text_key)
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
            "yes" if r["dropped"] else "no",
        ]
        for r in REASONS
    ]
    header = ["Reason", "Meaning", "Records", "Share", "Dropped"]
    return [header, *body, ["Total", "", summaries.num(total), summaries.pct(total, total), ""]]


def write_exclusions(parquet: Path, out: Path) -> list[str]:
    """Assign a reason to every row of the raw table and write them next to their keys."""
    rows = pq.read_table(parquet, columns=COLUMNS).to_pydict()
    reasons = assign_reasons(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys = {k: rows[k] for k in ("source_file", "record_index")}
    pq.write_table(pa.table({**keys, "reason": reasons}), out)
    return reasons


def main() -> None:
    """Assign reasons to the raw table at its default location and save the counts."""
    reasons = write_exclusions(
        Path("data/interim/records.parquet"), Path("data/interim/exclusions.parquet")
    )
    datasheet.write_csv(reason_counts(reasons), Path("reports/tables/exclusion_counts.csv"))


if __name__ == "__main__":
    main()
