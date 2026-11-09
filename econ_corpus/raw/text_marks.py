"""Used by step 2 of the pipeline: what the reasons take from the text of a record.

Input: the `text` column of the parquet written by `parse`.
Output: for every record, in row order, the share of common English words at the start of
its text, whether its first line is the rubric of an opinion page, and how many of its words
were written by its author.

Lives here: reading the texts once, and the rubrics. Does not live here: how the share is
computed (language), how the words of the author are counted (prose) or what a mark means
for a record (exclusions).

ProQuest files some opinion pages under a news section with a generic document type; the
only mark left is the rubric that the newspaper printed above the page, which the export
keeps as the first line of the text.
"""

from pathlib import Path
from typing import NamedTuple

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from econ_corpus.raw import language, prose

# Printed by USA Today above its debate and its columns from 1991 to 1997.
OPINION_RUBRIC_RE = r"^\s*THE EDITORIAL PAGE\b"
RUBRIC_CHARS = 60  # the rubric is the start of the first line


class Marks(NamedTuple):
    """What was read from the texts, one value per record."""

    english: list[float | None]
    rubric: list[bool]
    own_words: list[int]


def opinion_rubrics(texts: pa.Array | pa.ChunkedArray) -> list[bool]:
    """Tell, for each text, whether it starts with the rubric of an opinion page."""
    head = pc.utf8_slice_codeunits(texts, 0, RUBRIC_CHARS)
    return pc.fill_null(pc.match_substring_regex(head, OPINION_RUBRIC_RE), False).to_pylist()  # noqa: FBT003


def read(records: Path) -> Marks:
    """Return the marks of every record of the parquet, in row order.

    The texts are read one row group at a time: all together they do not fit in memory.
    """
    file = pq.ParquetFile(records)
    marks = Marks([], [], [])
    for group in range(file.num_row_groups):
        texts = file.read_row_group(group, columns=["text"])["text"]
        marks.english.extend(language.english_shares(texts))
        marks.rubric.extend(opinion_rubrics(texts))
        marks.own_words.extend(prose.own_word_counts(texts))
    return marks
