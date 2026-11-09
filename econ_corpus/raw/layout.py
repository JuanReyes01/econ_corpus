"""Used by step 1 of the pipeline: the layout of a ProQuest export file, and its check.

Input: one .txt export, as a path or as its text.
Output: its chunks, one per record plus the footer, and the result of the per-file check
(separators, records, footers, odd rules, and whether the file has the expected shape).

Lives here: reading a file, the separators and the footer, splitting a file into records
and the per-file sanity check. Does not live here: reading the fields of a record (fields,
labels) or building the table (parse).
"""

from pathlib import Path
import re

# --- File layout -----------------------------------------------------------------------
# Files are UTF-8 with CRLF line endings. A line of exactly 60 underscores precedes every
# record. The last separator is followed by a footer (contact and copyright lines), which
# is not a record, so a file with N records has N + 1 separators and N + 1 chunks after
# the first separator.
SEPARATOR = "_" * 60
SEPARATOR_RE = re.compile(rf"^{SEPARATOR}$", re.MULTILINE)
# Underscore rules of any other length appear inside article text; they are counted only
# to report them, never to split records.
NEAR_SEPARATOR_RE = re.compile(r"_{59,61}")  # a separator line with a slip in it
LOOSE_SEPARATOR_RE = re.compile(r"^_{20,}[ \t]*$", re.MULTILINE)
FOOTER_MARK = "Contáctenos en:"


def _chunks(text: str) -> list[str]:
    return SEPARATOR_RE.split(text.replace("\r\n", "\n"))


def split_records(text: str) -> list[str]:
    """Split a file into chunks, one per record plus the footer as the last one.

    The text before the first separator is dropped; a file should have nothing there.
    """
    return _chunks(text)[1:]


def read_text(path: Path) -> str:
    """Read a whole export file; 'utf-8-sig' drops a byte-order mark if there is one."""
    return Path(path).read_text(encoding="utf-8-sig", newline="")


def check_text(text: str, source_file: str) -> dict:
    """Check that a file has the shape the splitter relies on.

    A healthy file has exactly one footer, nothing before the first separator, and no line
    that is almost a separator (59 to 61 underscores once spaces are removed, but not the
    separator itself): it would not split, and two records would become one. Other rules of
    underscores (`odd_rules`) belong to article bodies; they are reported and are not
    failures. The records are not compared with a count from another source: ProQuest
    states none in the file.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    separators = sum(ln == SEPARATOR for ln in lines)
    odd_rules = len(LOOSE_SEPARATOR_RE.findall("\n".join(lines))) - separators
    chunks = _chunks(text)
    footers = sum(c.strip().startswith(FOOTER_MARK) for c in chunks[1:])
    records = len(chunks) - 1 - footers
    bare = ("".join(ln.split()) for ln in lines)  # without spaces, however they are written
    near = (bool(NEAR_SEPARATOR_RE.fullmatch(text)) for text in bare)
    spoiled = sum(ln != SEPARATOR and is_near for ln, is_near in zip(lines, near, strict=True))
    ok = footers == 1 and not chunks[0].strip() and spoiled == 0
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
