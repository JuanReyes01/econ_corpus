"""Tests for econ_corpus.export on tiny synthetic tables (no real article text)."""

import csv
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus import export, parse

TEXT = 'Line one, with a comma.\n\nA "quoted" line and\ttab.'
LEFT_OUT = ("file_footer", "duplicate_id")


def write_tables(tmp_path: Path, reasons: list[str], row_group: int = 1000) -> tuple[Path, Path]:
    """Write a records parquet and its exclusions parquet, one row per reason, in that order.

    Row 0 has awkward text; a row whose reason is `file_footer` is built as a footer.
    """
    rows = []
    for i, reason in enumerate(reasons):
        row = parse.empty_row("a.txt", i, is_footer=reason == "file_footer")
        if not row["is_footer"]:
            row |= {"title": f"Title {i}", "pub_date": date(2020, 1, 2), "doc_id": i}
            row |= {"text": TEXT if i == 0 else None, "url": "https://example.test/x"}
        rows.append(row)
    records = tmp_path / "records.parquet"
    pq.write_table(
        pa.Table.from_pylist(rows, schema=parse.SCHEMA), records, row_group_size=row_group
    )
    keys = {"source_file": ["a.txt"] * len(reasons), "record_index": list(range(len(reasons)))}
    exclusions = tmp_path / "exclusions.parquet"
    # A different row-group size from the records, so the two files do not line up by chance.
    pq.write_table(pa.table({**keys, "reason": reasons}), exclusions, row_group_size=row_group + 3)
    return records, exclusions


def read_back(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_csv_has_the_columns_of_the_table_in_order(tmp_path: Path) -> None:
    records, exclusions = write_tables(tmp_path, ["kept", "kept"])
    export.write_csv(records, exclusions, tmp_path / "r.csv")
    with (tmp_path / "r.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == parse.SCHEMA.names


def test_footers_and_repeated_ids_are_left_out_and_the_rest_stays_in_order(
    tmp_path: Path,
) -> None:
    reasons = ["kept", "duplicate_id", "not_opinion", "file_footer", "unclear_opinion"]
    records, exclusions = write_tables(tmp_path, reasons)
    assert export.write_csv(records, exclusions, tmp_path / "r.csv") == 3
    assert [r["record_index"] for r in read_back(tmp_path / "r.csv")] == ["0", "2", "4"]


def test_rows_that_are_not_opinion_or_are_not_queried_stay_in_the_raw_csv(
    tmp_path: Path,
) -> None:
    reasons = ["not_opinion", "not_queried_newspaper", "duplicate_text", "missing_metadata"]
    records, exclusions = write_tables(tmp_path, reasons)
    assert export.write_csv(records, exclusions, tmp_path / "r.csv") == 4


def test_text_with_commas_quotes_and_newlines_survives_the_round_trip(tmp_path: Path) -> None:
    records, exclusions = write_tables(tmp_path, ["kept", "kept"])
    export.write_csv(records, exclusions, tmp_path / "r.csv")
    rows = read_back(tmp_path / "r.csv")
    assert rows[0]["text"] == TEXT
    assert rows[0]["title"] == "Title 0"
    assert rows[0]["pub_date"] == "2020-01-02"
    assert rows[0]["url"] == "https://example.test/x"


def test_missing_values_are_empty_cells(tmp_path: Path) -> None:
    records, exclusions = write_tables(tmp_path, ["kept", "kept"])
    export.write_csv(records, exclusions, tmp_path / "r.csv")
    assert read_back(tmp_path / "r.csv")[1]["text"] == ""


def test_many_batches_keep_every_row_in_order(tmp_path: Path) -> None:
    reasons = [LEFT_OUT[i % 2] if i % 3 == 0 else "kept" for i in range(25)]
    records, exclusions = write_tables(tmp_path, reasons, row_group=5)
    export.write_csv(records, exclusions, tmp_path / "r.csv", batch_size=7)
    expected = [str(i) for i, reason in enumerate(reasons) if reason not in LEFT_OUT]
    assert [r["record_index"] for r in read_back(tmp_path / "r.csv")] == expected


def test_exclusions_that_do_not_match_the_table_are_refused(tmp_path: Path) -> None:
    records, _ = write_tables(tmp_path, ["kept", "kept", "kept"])
    other = tmp_path / "other"
    other.mkdir()
    _, short = write_tables(other, ["kept", "kept"])
    with pytest.raises(ValueError, match="rows"):
        export.write_csv(records, short, tmp_path / "r.csv")
