"""The reasons table: why a row of the parsed table is left out, as data.

Input: none for the table itself; `write_reasons` and `load` take the records a reason was
decided from.
Output: `REASONS`, one entry per reason, and `LEFT_OUT`, the codes of rows that are not part of
the shared raw table; a reasons file tied to its records, and its reasons read back.

Lives here: the codes, their meaning, the two flags, and the file that holds one reason per
row. Does not live here: the rules that assign a reason (exclusions) or what is done with the
flags (export, datasheet).

`in_raw` says whether a row belongs to the shared raw table (footers and repeats do not);
`dropped` says whether it leaves the cleaned dataset. Each row gets exactly one reason.
"""

import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus import parse

# The reasons table: code and meaning, in the order the rules are applied.
REASONS = [
    {
        "code": "file_footer",
        "description": "Row is the footer of an export file, not an article",
        "in_raw": False,
        "dropped": True,
    },
    {
        "code": "duplicate_id",
        "description": "Repeats a ProQuest id; the copy with the longest body is the one kept",
        "in_raw": False,
        "dropped": True,
    },
    {
        "code": "not_queried_newspaper",
        "description": "Publication is not one of the queried newspapers",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "duplicate_text",
        "description": "Same text in the same newspaper as another record, which stays",
        "in_raw": False,
        "dropped": True,
    },
    {
        "code": "missing_metadata",
        "description": "No publication, no id, or no document type and section: unclassifiable",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "not_opinion",
        "description": "A news section, and neither an opinion document type nor an opinion title",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "unclear_opinion",
        "description": "Generic document type, no section and no opinion title: may be opinion",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "no_text",
        "description": "Opinion piece with no text, or only a notice shared by several articles",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "no_author",
        "description": "Opinion piece that is unsigned or marked Anonymous",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "no_person_author",
        "description": "Byline names no person (an institution, or text with no full name)",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "kept",
        "description": "Opinion piece with text, signed by at least one person",
        "in_raw": True,
        "dropped": False,
    },
]

LEFT_OUT = [r["code"] for r in REASONS if not r["in_raw"]]

KEYS = ["source_file", "record_index"]
# The columns a reason is decided from: a change in any of them makes the reasons stale.
INPUTS = [
    *KEYS, "is_footer", "doc_id", "body_sha256", "title", "pub_date", "publication_key",
    "doc_type", "section", "body_chars", "body_words", "author",
]  # fmt: skip
RECORDS_STAMP = "records"  # metadata key of the reasons file that holds their fingerprint
RULES_STAMP = "rules"  # and the one that holds the fingerprint of the code


def rules_fingerprint(package: Path | None = None) -> str:
    """Return a short code that changes whenever a module of the package changes.

    A reason follows from the records and from the rules. Any edit counts, since telling a
    rule from a comment is not worth the risk of keeping reasons that no longer hold.
    """
    digest = hashlib.sha256()
    for module in sorted((package or Path(__file__).parent).glob("*.py")):
        digest.update(module.name.encode() + module.read_bytes())
    return digest.hexdigest()[:16]


def file_digest(path: Path) -> str:
    """Return a short code that changes whenever a byte of the file changes."""
    digest = hashlib.blake2b(digest_size=8)
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 24):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(table: pa.Table) -> str:
    """Return a short code that changes whenever a value of the table changes.

    The rows are hashed as CSV text, so the code does not depend on how the file was written.
    """
    digest = hashlib.sha256(",".join(table.column_names).encode())
    options = pacsv.WriteOptions(include_header=False)
    for batch in table.to_batches():
        sink = pa.BufferOutputStream()
        pacsv.write_csv(batch, sink, options)
        digest.update(sink.getvalue())
    return digest.hexdigest()[:16]


def check_parser(records: Path) -> None:
    """Refuse a table of records that this version of the parser did not write."""
    written_by = (pq.read_schema(records).metadata or {}).get(parse.STAMP.encode(), b"").decode()
    if written_by != parse.code_fingerprint():
        msg = f"{records.name} was written by another version of parse.py: run parse again"
        raise ValueError(msg)


def write_reasons(
    rows: pa.Table,
    codes: list[str],
    out: Path,
    stamps: dict[str, str] | None = None,
    row_group_size: int | None = None,
) -> None:
    """Write one reason per row of the records, next to its keys.

    The file carries a fingerprint of the columns the reasons were decided from, plus the
    stamps of the caller, so `load` can refuse it once the records change.
    """
    rows = rows.select(INPUTS)
    table = pa.table({**{key: rows[key] for key in KEYS}, "reason": codes})
    stamps = {**(stamps or {}), RECORDS_STAMP: fingerprint(rows), RULES_STAMP: rules_fingerprint()}
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table.replace_schema_metadata(stamps), out, row_group_size=row_group_size)


def load(records: Path, reasons: Path) -> pa.ChunkedArray:
    """Return the reason of every row of `records`, in order.

    The reasons file must hold the same rows in the same order and must have been computed
    from these records with the rules as they are now: one written for another parse or by
    older code would put the reasons on the wrong records, or keep reasons that no longer
    hold, so it is refused.
    """
    table = pq.read_table(reasons, columns=[*KEYS, "reason"])
    rows = pq.read_table(records, columns=INPUTS)
    if not table.select(KEYS).equals(rows.select(KEYS)):
        msg = f"the rows of {reasons.name} and {records.name} differ: run the exclusions again"
        raise ValueError(msg)
    check_parser(records)
    stamps = pq.read_schema(reasons).metadata or {}
    found = {
        "it has no fingerprint": RECORDS_STAMP.encode() not in stamps,
        f"{records.name} changed since (another parse)": stamps.get(RECORDS_STAMP.encode(), b"")
        != fingerprint(rows).encode(),
        "the rules changed since (the code was edited)": stamps.get(RULES_STAMP.encode(), b"")
        != rules_fingerprint().encode(),
    }
    wrong = next((why for why, bad in found.items() if bad), None)
    if wrong:
        msg = f"{reasons.name} cannot be used: {wrong}. Run the exclusions again"
        raise ValueError(msg)
    return table["reason"]
