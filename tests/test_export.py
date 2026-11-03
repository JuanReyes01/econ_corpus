"""Tests for econ_corpus.export on tiny synthetic tables (no real article text)."""

import csv
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from econ_corpus import export, parse

TEXT = 'Line one, with a comma.\n\nA "quoted" line and\ttab.'


def write_table(path: Path, n_rows: int = 3) -> None:
    """Write a parquet with the real schema; row 0 has awkward text, the last is a footer."""
    rows = []
    for i in range(n_rows):
        row = parse.empty_row("a.txt", i, is_footer=i == n_rows - 1)
        if not row["is_footer"]:
            row |= {"title": f"Title {i}", "pub_date": date(2020, 1, 2), "doc_id": i}
            row |= {"text": TEXT if i == 0 else None, "url": "https://example.test/x"}
        rows.append(row)
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), path)


def read_back(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_csv_has_the_columns_of_the_table_in_order(tmp_path: Path) -> None:
    write_table(tmp_path / "r.parquet")
    export.write_csv(tmp_path / "r.parquet", tmp_path / "r.csv")
    with (tmp_path / "r.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == parse.SCHEMA.names


def test_csv_has_one_row_per_table_row_footer_included(tmp_path: Path) -> None:
    write_table(tmp_path / "r.parquet", n_rows=4)
    assert export.write_csv(tmp_path / "r.parquet", tmp_path / "r.csv") == 4
    assert len(read_back(tmp_path / "r.csv")) == 4


def test_text_with_commas_quotes_and_newlines_survives_the_round_trip(tmp_path: Path) -> None:
    write_table(tmp_path / "r.parquet")
    export.write_csv(tmp_path / "r.parquet", tmp_path / "r.csv")
    rows = read_back(tmp_path / "r.csv")
    assert rows[0]["text"] == TEXT
    assert rows[0]["title"] == "Title 0"
    assert rows[0]["pub_date"] == "2020-01-02"
    assert rows[0]["url"] == "https://example.test/x"


def test_missing_values_are_empty_cells(tmp_path: Path) -> None:
    write_table(tmp_path / "r.parquet")
    export.write_csv(tmp_path / "r.parquet", tmp_path / "r.csv")
    rows = read_back(tmp_path / "r.csv")
    assert rows[1]["text"] == ""
    assert rows[2]["is_footer"] == "true"


def test_many_batches_keep_every_row_in_order(tmp_path: Path) -> None:
    write_table(tmp_path / "r.parquet", n_rows=25)
    export.write_csv(tmp_path / "r.parquet", tmp_path / "r.csv", batch_size=7)
    assert [r["record_index"] for r in read_back(tmp_path / "r.csv")] == [
        str(i) for i in range(25)
    ]
