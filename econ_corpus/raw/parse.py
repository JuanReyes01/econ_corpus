"""Step 1 of the pipeline: turn raw ProQuest .txt exports into one flat table.

Input: the .txt files ProQuest produces, each holding hundreds of records.
Output: a parquet table with one row per record. Each row has every metadata field that
the export contains (one column per label), the parsed dates, years and ids, the provenance
(`source_file`, `record_index`), a hash and word count of the body and the body text itself.

Lives here: building a row from a record, the schema and the stamp of the table, and the
streaming parquet writer that replaces the table only when every file passes its check.
Does not live here: the layout of a file and its check (layout), finding the fields of a
record (fields), the label tables and the parsing of values (labels), deciding which records
to keep (exclusions) or describing them (datasheet).

Nothing is dropped silently. A value that cannot be parsed stays in the table with a
status column ('missing', 'unparseable', ...) so later stages can count it.
"""

import hashlib
from pathlib import Path
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from econ_corpus.raw.fields import BODY_LABEL, read_header, read_metadata
from econ_corpus.raw.labels import (
    HEADER_LABELS,
    HEADER_URL,
    KEY_COLUMNS,
    METADATA_COLS,
    compact,
    parse_date,
    parse_int,
)
from econ_corpus.raw.layout import FOOTER_MARK, check_text, read_text, split_records

STR_COLS = ["source_file", *METADATA_COLS, *HEADER_LABELS.values(), HEADER_URL]
STR_COLS += [f"{c}_key" for c in KEY_COLUMNS]
STR_COLS += ["date_status", "year_status", "id_status", "body_sha256"]
STAMP = "parse"  # metadata key of the table that says which parser wrote it
# The modules whose code decides the parsed table, by their path inside the package, sorted.
PARSER_MODULES = ("raw/fields.py", "raw/labels.py", "raw/layout.py", "raw/parse.py")


def code_fingerprint(package: Path | None = None) -> str:
    """Return a short code that changes whenever a module of the parser changes.

    Every module of PARSER_MODULES is hashed with its path inside the package, so an edit in
    any of them, or a module moved, gives another code.
    """
    root = package or Path(__file__).parents[1]
    digest = hashlib.sha256()
    for module in PARSER_MODULES:
        digest.update(module.encode() + (root / module).read_bytes())
    return digest.hexdigest()[:16]


def stamp() -> dict[str, str]:
    """Return the metadata a table of records carries: the fingerprint of its parser.

    The later steps refuse a table written by another version of the parser (any module of
    PARSER_MODULES), so an edit there cannot leave old records in use.
    """
    return {STAMP: code_fingerprint()}


SCHEMA = pa.schema(
    [(c, pa.string()) for c in STR_COLS]
    + [(c, pa.int64()) for c in ("record_index", "pub_year", "date_year", "doc_id")]
    + [(c, pa.int64()) for c in ("n_meta_fields", "body_words", "body_chars")]
    + [(c, pa.bool_()) for c in ("is_footer", "has_materia", "has_body")]
    + [("pub_date", pa.date32()), ("text", pa.string())],
    metadata=stamp(),
)


def empty_row(source_file: str, record_index: int, *, is_footer: bool) -> dict:
    """Return a row with every column present, all values empty or 'missing'."""
    row = dict.fromkeys(SCHEMA.names)
    row |= {"source_file": source_file, "record_index": record_index, "is_footer": is_footer}
    row |= {"has_materia": False, "has_body": False, "n_meta_fields": 0}
    row |= {"body_words": 0, "body_chars": 0}
    row |= {"date_status": "missing", "year_status": "missing", "id_status": "missing"}
    return row


def parse_record(chunk: str, source_file: str, record_index: int) -> dict:
    """Parse one chunk into a row; metadata values are normalised, the body is not touched."""
    if chunk.strip().startswith(FOOTER_MARK):
        return empty_row(source_file, record_index, is_footer=True)
    row = empty_row(source_file, record_index, is_footer=False)
    lines = chunk.replace("\r\n", "\n").split("\n")
    body_at = next((i for i, ln in enumerate(lines) if ln.startswith(BODY_LABEL)), None)
    # The walk must not go above the body line, or it could read header lines as metadata.
    fields, meta_start = read_metadata(lines, body_at or 0)
    body = ""
    if body_at is not None:
        # The body starts on the 'Texto completo:' line and ends where the metadata begins.
        first = lines[body_at][len(BODY_LABEL) :]
        body = "\n".join([first, *lines[body_at + 1 : meta_start]]).strip()
    header = read_header(lines[:body_at]) if body_at is not None else {}
    for col in (*METADATA_COLS, *HEADER_LABELS.values(), HEADER_URL):
        row[col] = fields.get(col) or header.get(col) or None
    for col in KEY_COLUMNS:
        row[f"{col}_key"] = compact(row[col]) if row[col] else None
    row["pub_date"], row["date_year"], row["date_status"] = parse_date(row["date_raw"])
    row["pub_year"], row["year_status"] = parse_int(row["year_raw"], 1500, 2100)
    row["doc_id"], row["id_status"] = parse_int(row["id_raw"])
    row |= {"has_materia": "subject" in fields, "n_meta_fields": len(fields)}
    if body:
        row |= {"has_body": True, "body_words": len(body.split()), "body_chars": len(body)}
        row["body_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        row["text"] = body
    return row


def parse_text(text: str, source_file: str) -> list[dict]:
    """Parse the text of one file into rows, numbering records from 0 in file order."""
    return [parse_record(c, source_file, i) for i, c in enumerate(split_records(text))]


def write_parquet(paths: list[Path], out: Path) -> list[dict]:
    """Parse files one at a time into a parquet table; return one sanity result per file.

    Only one file is in memory at a time, so the whole corpus never has to fit in RAM.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    with pq.ParquetWriter(out, SCHEMA, compression="zstd") as writer:
        for path in paths:
            text, name = read_text(path), Path(path).name
            writer.write_table(pa.Table.from_pylist(parse_text(text, name), schema=SCHEMA))
            checks.append(check_text(text, name))
    return checks


def parse_folder(raw_dir: Path, out: Path) -> list[dict]:
    """Parse every .txt export of a folder, in file-name order; return the sanity checks.

    The table is written under another name and takes its place only if every file passes
    its check, so a parse that fails never replaces a good table.
    """
    paths = sorted(Path(raw_dir).glob("*.txt"))
    if not paths:
        msg = f"no .txt exports in {raw_dir}"
        raise FileNotFoundError(msg)
    partial = out.with_name(out.name + ".tmp")
    try:
        checks = write_parquet(paths, partial)
        failed = [c["source_file"] for c in checks if not c["ok"]]
        if failed:
            msg = "files that failed the sanity check: " + ", ".join(failed)
            raise ValueError(msg)
        partial.replace(out)
    finally:
        partial.unlink(missing_ok=True)
    return checks


def main() -> None:
    """Parse the folder given on the command line into the repo's default table."""
    checks = parse_folder(Path(sys.argv[1]), Path("data/interim/records.parquet"))
    records = sum(c["records"] for c in checks)
    print(f"{len(checks):,} files, {records:,} records, every file passed the check")  # noqa: T201


if __name__ == "__main__":
    main()
