"""Tell whether a text is written in English, from the commonest English words.

Input: the texts of the records (the `text` column of the parquet written by `parse`).
Output: for each text, the share of the words at its start that are common English words.

Lives here: the word list, how much of a text is read, and the share under which a text is
not English. Does not live here: what is done with a text that is not English (exclusions).

In English prose the words of `ENGLISH_WORDS` are a fifth to a third of all words; in a text
in Spanish, Portuguese, French, Turkish, Arabic or Russian they are close to none. No other
language is named: the share only says whether the text is English.
"""

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ENGLISH_WORDS = (
    "the", "of", "and", "to", "in", "that", "is", "for", "it", "was", "with", "as", "on", "be",
    "at", "by", "this", "have", "from", "or", "had", "not", "are", "but", "his", "they", "which",
    "you", "were", "their", "would", "there", "been", "will", "who", "more", "when", "what",
    "about",
)  # fmt: skip
PATTERN = rf"(?i)\b(?:{'|'.join(ENGLISH_WORDS)})\b"
# A letter outside a-z, or an accent on its own. The `\b` of the pattern only knows the letters
# a-z, so without this 'not' would be found in 'notícias' and 'as' in 'crianças'.
OTHER_LETTER = r"[^\P{L}a-zA-Z]|\p{M}"
HEAD_CHARS = 2000  # characters read at the start of a text: enough to tell, and quick
MIN_ENGLISH = 0.05  # under this share of common English words a text is not English


def english_shares(texts: pa.Array | pa.ChunkedArray) -> list[float | None]:
    """Return, for each text, the share of its first words that are common English words.

    A missing text and a text with no words have no share.
    """
    head = pc.utf8_slice_codeunits(texts, 0, HEAD_CHARS)
    head = pc.replace_substring_regex(head, OTHER_LETTER, "x")
    words = pc.count_substring_regex(head, r"\S+").to_pylist()
    found = pc.count_substring_regex(head, PATTERN).to_pylist()
    return [hits / total if total else None for hits, total in zip(found, words, strict=True)]


def shares_of(records: Path) -> list[float | None]:
    """Return the share of every record of the parquet, in row order.

    The texts are read one row group at a time: all together they do not fit in memory.
    """
    file = pq.ParquetFile(records)
    return [
        share
        for group in range(file.num_row_groups)
        for share in english_shares(file.read_row_group(group, columns=["text"])["text"])
    ]
