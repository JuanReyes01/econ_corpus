"""Used by step 1 of the pipeline: find the labelled fields of one record.

Input: the lines of one record.
Output: its metadata fields and the line where they begin, and the fields of its header
(the document link, the abstract and the links).

Lives here: walking the metadata block and the header of a record. Does not live here: the
label tables and the parsing of values (labels), splitting a file into records (layout) or
building the row (parse).
"""

import re

from econ_corpus.raw.labels import HEADER_KEYS, HEADER_URL, LABEL_KEYS, compact

# A record is: title, header lines, then 'Texto completo:' followed by the body, then a
# block of 'Label: value' metadata lines separated by blank lines.
BODY_LABEL = "Texto completo:"
LABEL_RE = re.compile(r"([^:]{2,60}):\s?(.*)", re.DOTALL)


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
    stopping at the first block without a known label or with a label already read, leaves
    the body intact.
    """
    fields, meta_start = {}, len(lines)
    for start, end in reversed(_blocks(lines, floor)):
        m = LABEL_RE.match(lines[start])
        key = LABEL_KEYS.get(compact(m[1])) if m else None
        if key is None or key in fields:
            # A label read twice: the block above is a paragraph of the body that happens to
            # start like a label, and the real field is the one already read.
            break
        fields[key] = _value(m[2], lines[start + 1 : end])
        meta_start = start
    return fields, meta_start


def _value(first: str, rest: list[str]) -> str:
    """Join a label's value; lines under the label without a blank line continue it."""
    return " ".join(p.strip() for p in [first, *rest] if p.strip())


def read_header(lines: list[str]) -> dict[str, str]:
    """Read the header lines above 'Texto completo:': the document link, abstract and links."""
    fields: dict[str, str] = {}
    for start, end in _blocks(lines, 0):
        m = LABEL_RE.match(lines[start])
        key = HEADER_KEYS.get(compact(m[1])) if m else None
        if key:
            fields[key] = _value(m[2], lines[start + 1 : end])
        elif lines[start].startswith("http"):
            fields.setdefault(HEADER_URL, _value(lines[start], lines[start + 1 : end]))
    return fields
