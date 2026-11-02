"""Stage 1 of the pipeline: turn raw ProQuest .txt exports into one flat table.

Input: the .txt files ProQuest produces, each holding hundreds of records.
Output: a parquet table with one row per record. Each row has the parsed metadata, the
provenance (`source_file`, `record_index`) and a hash and word count of the body, never
the body text itself, so the licensed text is not copied.

Lives here: splitting files into records, reading fields, normalising metadata values,
parsing dates, years and ids, the per-file sanity check and the streaming parquet writer.
Does not live here: deciding which records to keep (exclusions) or measuring quality (audit).

Nothing is dropped silently. A value that cannot be parsed stays in the table with a
status column ('missing', 'unparseable', ...) so later stages can count it.
"""

from collections.abc import Iterator
from datetime import date
import hashlib
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.parquet as pq

# --- File layout -----------------------------------------------------------------------
# Files are UTF-8 with CRLF line endings. A line of exactly 60 underscores precedes every
# record. The last separator is followed by a footer (contact and copyright lines), which
# is not a record, so a file with N records has N + 1 separators and N + 1 chunks after
# the first separator.
SEPARATOR = "_" * 60
SEPARATOR_RE = re.compile(rf"^{SEPARATOR}$", re.MULTILINE)
# Underscore rules of any other length appear inside article text; they are counted only
# to report them, never to split records.
LOOSE_SEPARATOR_RE = re.compile(r"^_{20,}[ \t]*$", re.MULTILINE)
FOOTER_MARK = "Contáctenos en:"

# A record is: title, header lines, then 'Texto completo:' followed by the body, then a
# block of 'Label: value' metadata lines separated by blank lines.
BODY_LABEL = "Texto completo:"
LABEL_RE = re.compile(r"([^:]{2,60}):\s?(.*)", re.DOTALL)

# English month prefixes, lower-cased: ProQuest writes dates like 'Nov 9, 2022' even though
# the labels are Spanish.
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

# Metadata labels we keep (Spanish label -> column).
KEPT_LABELS = {
    "Título": "title",
    "Autor": "author",
    "Título de publicación": "publication",
    "Año de publicación": "year_raw",
    "Fecha de publicación": "date_raw",
    "Sección": "section",
    "Idioma de la publicación": "language",
    "Tipo de fuente": "source_type",
    "Tipo de documento": "doc_type",
    "ID del documento de ProQuest": "id_raw",
}
# Labels we do not keep but must recognise, otherwise the metadata walk (see
# `read_metadata`) stops at them and the fields above them are lost into the body.
# The list was built from the data: the first full run showed which labels were missing.
SEEN_LABELS = [
    "Materia", "Lugar", "Personas", "Empresa/organización", "Término de indexación de negocios",
    "Identificador / palabra clave", "Clasificación", "Lugar y fecha de origen", "Páginas",
    "Número de páginas", "Primera página", "ISSN", "CODEN", "Editorial", "Lugar de publicación",
    "País de publicación", "Materia de publicación", "URL del documento", "Copyright",
    "Última actualización", "Base de datos", "Disponibilidad de texto completo", "e-ISSN",
    "columna", "Número de acceso", "Fecha del hito", "Características del documento",
    "Detalles de fuente", "Número", "Autor corporativo/institucional",
]  # fmt: skip
# Columns that also get a `<column>_key` copy used to compare categories.
KEY_COLUMNS = ["language", "source_type", "doc_type", "publication"]


def compact(value: str) -> str:
    """Remove every whitespace character and casefold.

    ProQuest inserts stray spaces inside metadata values ('En glish'), so the compacted
    form is the safe key for comparing categories.
    """
    return re.sub(r"\s+", "", value).casefold()


# Labels are matched through `compact` too, so a stray space in a label does not break it.
# Kept labels map to their column name, the others to their own Spanish name.
LABEL_KEYS = {compact(k): v for k, v in KEPT_LABELS.items()} | {compact(k): k for k in SEEN_LABELS}

STR_COLS = ["source_file", *KEPT_LABELS.values(), *[f"{c}_key" for c in KEY_COLUMNS]]
STR_COLS += ["date_status", "year_status", "id_status", "body_sha256"]
SCHEMA = pa.schema(
    [(c, pa.string()) for c in STR_COLS]
    + [(c, pa.int64()) for c in ("record_index", "pub_year", "date_year", "doc_id")]
    + [(c, pa.int64()) for c in ("n_meta_fields", "body_words", "body_chars")]
    + [(c, pa.bool_()) for c in ("is_footer", "has_materia", "has_body")]
    + [("pub_date", pa.date32())]
)


def parse_int(raw: str | None, lo: int = 0, hi: int = 10**15) -> tuple[int | None, str]:
    """Parse a digits-only integer after removing stray spaces.

    Returns (value, status) where status is 'ok', 'missing' or 'unparseable'.
    """
    if raw is None:
        return None, "missing"
    digits = compact(raw)
    if digits.isascii() and digits.isdigit() and lo <= int(digits) <= hi:
        return int(digits), "ok"
    return None, "unparseable"


def parse_date(raw: str | None) -> tuple[date | None, int | None, str]:
    """Parse a publication date such as 'Nov 9, 2022', or a bare year.

    Returns (date, year, status) where status is 'ok', 'year_only', 'missing' or
    'unparseable'. A year-only value gives no date but keeps the year.
    """
    if raw is None:
        return None, None, "missing"
    text = compact(raw)
    if re.fullmatch(r"\d{4}", text):
        return None, int(text), "year_only"
    # After `compact` the date has no spaces: 'Nov 9, 2022' -> 'nov9,2022'.
    m = re.fullmatch(r"([a-z]{3,9})(\d{1,2}),(\d{4})", text)
    if m and m[1][:3] in MONTHS:
        try:
            parsed = date(int(m[3]), MONTHS.index(m[1][:3]) + 1, int(m[2]))
        except ValueError:  # impossible day, such as Feb 30
            return None, None, "unparseable"
        return parsed, parsed.year, "ok"
    return None, None, "unparseable"


def _chunks(text: str) -> list[str]:
    return SEPARATOR_RE.split(text.replace("\r\n", "\n"))


def split_records(text: str) -> list[str]:
    """Split a file into chunks, one per record plus the footer as the last one.

    The text before the first separator is dropped; a file should have nothing there.
    """
    return _chunks(text)[1:]


def _blocks(lines: list[str], floor: int) -> list[tuple[int, int]]:
    """Return runs of non-blank lines as (start, end) index pairs, from `floor` on."""
    out, start = [], None
    for i in range(floor, len(lines)):
        if lines[i].strip():
            start = i if start is None else start
        elif start is not None:
            out.append((start, i))
            start = None
    return out + ([(start, len(lines))] if start is not None else [])


def read_metadata(lines: list[str], floor: int) -> tuple[dict[str, str], int]:
    """Read the metadata block of a record, returning (fields, index of its first line).

    The block is walked backwards from the end, one blank-separated block at a time, for
    as long as each block starts with a known label. Scanning forward cannot work: the
    optional 'Materia' line means there is no fixed first label, and body lines such as
    'Credit: ...' look exactly like labels. Walking back from 'Base de datos', and
    stopping at the first block without a known label, leaves the body intact.
    """
    fields, meta_start = {}, len(lines)
    for start, end in reversed(_blocks(lines, floor)):
        m = LABEL_RE.match(lines[start])
        key = LABEL_KEYS.get(compact(m[1])) if m else None
        if key is None:
            break
        # Lines under the label without a blank line between them continue its value.
        parts = [m[2], *lines[start + 1 : end]]
        fields[key] = " ".join(p.strip() for p in parts if p.strip())
        meta_start = start
    return fields, meta_start


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
    for col in KEPT_LABELS.values():
        row[col] = fields.get(col) or None
    for col in KEY_COLUMNS:
        row[f"{col}_key"] = compact(row[col]) if row[col] else None
    row["pub_date"], row["date_year"], row["date_status"] = parse_date(row["date_raw"])
    row["pub_year"], row["year_status"] = parse_int(row["year_raw"], 1500, 2100)
    row["doc_id"], row["id_status"] = parse_int(row["id_raw"])
    row |= {"has_materia": "Materia" in fields, "n_meta_fields": len(fields)}
    if body:
        row |= {"has_body": True, "body_words": len(body.split()), "body_chars": len(body)}
        row["body_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return row


def read_text(path: Path) -> str:
    """Read a whole export file; 'utf-8-sig' drops a byte-order mark if there is one."""
    return Path(path).read_text(encoding="utf-8-sig", newline="")


def parse_text(text: str, source_file: str) -> list[dict]:
    """Parse the text of one file into rows, numbering records from 0 in file order."""
    return [parse_record(c, source_file, i) for i, c in enumerate(split_records(text))]


def check_text(text: str, source_file: str) -> dict:
    """Compare records found against separator lines counted independently.

    A healthy file has exactly one footer, nothing before the first separator, and as many
    chunks as separators. `odd_rules` counts other underscore rules, which are reported
    but are not failures.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    separators = sum(ln == SEPARATOR for ln in lines)
    odd_rules = len(LOOSE_SEPARATOR_RE.findall("\n".join(lines))) - separators
    chunks = _chunks(text)
    footers = sum(c.strip().startswith(FOOTER_MARK) for c in chunks[1:])
    records = len(chunks) - 1 - footers
    ok = records + footers == separators and footers == 1 and not chunks[0].strip()
    return {
        "source_file": source_file,
        "separators": separators,
        "records": records,
        "footers": footers,
        "odd_rules": odd_rules,
        "ok": ok,
    }


def sanity_check(path: Path) -> dict:
    """Run `check_text` on a file on disk."""
    return check_text(read_text(path), Path(path).name)


def iter_file(path: Path) -> Iterator[dict]:
    """Yield the parsed rows of one file on disk."""
    yield from parse_text(read_text(path), Path(path).name)


def write_parquet(paths: list[Path], out: Path) -> list[dict]:
    """Parse files one at a time into a parquet table; return one sanity result per file.

    Only one file is in memory at a time, so the whole corpus never has to fit in RAM.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    with pq.ParquetWriter(out, SCHEMA) as writer:
        for path in paths:
            text, name = read_text(path), Path(path).name
            writer.write_table(pa.Table.from_pylist(parse_text(text, name), schema=SCHEMA))
            checks.append(check_text(text, name))
    return checks
