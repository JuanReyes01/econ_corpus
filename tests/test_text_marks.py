"""Tests for econ_corpus.raw.text_marks on made-up texts."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus.raw import language, prose, text_marks

ENGLISH = "The price of bread went up again, and it is not the first time that it has."
SPANISH = "El precio del pan volvió a subir este año, y no es la primera vez que pasa."
RUBRIC = "THE EDITORIAL PAGE"


def rubrics(*texts: str | None) -> list[bool]:
    return text_marks.opinion_rubrics(pa.array(texts, type=pa.string()))


@pytest.mark.parametrize(
    "text",
    [
        f"{RUBRIC}\nToday's debate is on the price of bread. {ENGLISH}",
        f"{RUBRIC}; LETTERS {ENGLISH}",
        f"  {RUBRIC};Today's debate: BREAD",
    ],
)
def test_a_text_that_starts_with_the_rubric_of_the_editorial_page_is_marked(text: str) -> None:
    assert rubrics(text) == [True]


@pytest.mark.parametrize(
    "text",
    [
        ENGLISH,
        f"{ENGLISH} {RUBRIC}",  # the rubric is the first line, not a phrase of the text
        f"A SPECIAL REPORT: BREAD; {RUBRIC}",  # only at the very start
        "The editorial page of this newspaper said so.",
        "THE EDITORIAL PAGES of two newspapers agree.",
        "",
        None,
    ],
)
def test_other_texts_carry_no_rubric(text: str | None) -> None:
    assert rubrics(text) == [False]


def test_the_marks_of_a_table_of_records_come_in_row_order(tmp_path: Path) -> None:
    records = tmp_path / "records.parquet"
    texts = [ENGLISH, None, f"{RUBRIC}\n{ENGLISH}", SPANISH, f"{RUBRIC}\n{SPANISH}"]
    table = pa.table({"text": pa.array(texts, type=pa.string())})
    pq.write_table(table, records, row_group_size=2)
    assert pq.ParquetFile(records).num_row_groups > 1
    marks = text_marks.read(records)
    assert marks.rubric == [False, False, True, False, True]
    assert marks.english == language.english_shares(pa.array(texts, type=pa.string()))
    assert marks.own_words == prose.own_word_counts(pa.array(texts, type=pa.string()))
    assert marks.own_words[1] == 0
    assert marks.own_words[0] == len(ENGLISH.split())
