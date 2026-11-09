"""Tests for econ_corpus.processed on tiny synthetic tables (made-up names, no article text)."""

import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from econ_corpus import parse, processed

A, B = "Example Daily", "Sample Times"
NYT = "newyorktimes,lateedition(eastcoast);newyork,n.y."


def tables_for(*rows: tuple[int, str, str]) -> dict[str, list[list[str]]]:
    """Build the author tables from (doc id, byline, newspaper) rows."""
    ids, bylines, papers = zip(*rows, strict=True)
    return processed.author_tables(list(ids), list(bylines), list(papers))


def body(table: list[list[str]]) -> list[list[str]]:
    return table[1:]


# --- authors, their names and the links ---------------------------------------------


def test_each_person_becomes_one_author_numbered_in_name_key_order() -> None:
    tables = tables_for((10, "Roe, Richard; Doe, Jane", A), (11, "Poe, Ann", A))
    assert tables["authors"] == [
        ["author_id", "name", "articles", "name_variants"],
        ["1", "Ann Poe", "1", "1"],
        ["2", "Jane Doe", "1", "1"],
        ["3", "Richard Roe", "1", "1"],
    ]


def test_links_keep_the_byline_order_and_how_the_name_was_read() -> None:
    tables = tables_for((10, "Roe, Richard; Jane Doe. Springfield", A))
    assert tables["article_authors"] == [
        ["doc_id", "author_id", "position", "read"],
        ["10", "2", "1", "as_written"],
        ["10", "1", "2", "recovered"],
    ]


def test_variants_of_one_author_share_an_id_and_are_listed_with_the_rule() -> None:
    tables = tables_for((10, "Doe, Jane", A), (11, "Doe, Jane", A), (12, "DOE, JANE Q", A))
    assert body(tables["authors"]) == [["1", "Jane Doe", "3", "2"]]
    assert tables["author_names"] == [
        ["author_id", "name", "name_key", "articles", "rule"],
        ["1", "Jane Doe", "janedoe", "2", "main"],
        ["1", "Jane Q Doe", "janeqdoe", "1", "shared_newspaper"],
    ]
    assert [row[1] for row in body(tables["article_authors"])] == ["1", "1", "1"]


def test_spelling_variants_with_one_key_show_the_commonest_spelling() -> None:
    tables = tables_for((10, "DOE, JANE", A), (11, "Doe, Jane", A), (12, "Doe, Jane", A))
    assert body(tables["author_names"]) == [["1", "Jane Doe", "janedoe", "3", "main"]]


def test_an_author_named_twice_in_a_byline_is_linked_once() -> None:
    tables = tables_for((10, "Doe, Jane; Doe, Jane Q", A))
    assert body(tables["article_authors"]) == [["10", "1", "1", "as_written"]]
    assert body(tables["authors"]) == [["1", "Jane Q Doe", "1", "2"]]


def test_a_name_written_twice_in_a_byline_counts_one_article() -> None:
    tables = tables_for((10, "Doe, Jane; DOE, JANE", A))
    assert body(tables["author_names"]) == [["1", "Jane Doe", "janedoe", "1", "main"]]
    assert body(tables["authors"]) == [["1", "Jane Doe", "1", "1"]]


def test_parts_that_name_nobody_leave_no_link() -> None:
    tables = tables_for((10, "The Editorial Board; Doe, Jane", A))
    assert body(tables["article_authors"]) == [["10", "1", "1", "as_written"]]


def test_doubtful_pairs_are_listed_with_names_and_article_counts() -> None:
    tables = tables_for((10, "Doe, Jane", A), (11, "Doe, Jane", A), (12, "Doe, Jane Q", B))
    assert tables["author_candidates"] == [
        ["author_id_a", "name_a", "articles_a", "author_id_b", "name_b", "articles_b", "kind"],
        ["1", "Jane Doe", "2", "2", "Jane Q Doe", "1", "no_shared_newspaper"],
    ]


# --- files --------------------------------------------------------------------------


def write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Write a records parquet and its reasons: two kept articles, one dropped, one footer."""
    rows = []
    bylines = ["Doe, Jane", "The Editorial Board", "Roe, Richard; Doe, Jane", None]
    for i, byline in enumerate(bylines):
        row = parse.empty_row("a.txt", i, is_footer=i == len(bylines) - 1)
        if not row["is_footer"]:
            row |= {"doc_id": 100 + i, "author": byline, "publication_key": NYT}
            row |= {"title": f"Title {i}", "text": f"Synthetic body {i}.", "has_body": True}
        rows.append(row)
    records = tmp_path / "records.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records, row_group_size=2)
    reasons = tmp_path / "exclusions.parquet"
    codes = ["kept", "no_person_author", "kept", "file_footer"]
    pq.write_table(pa.table({"reason": codes}), reasons, row_group_size=3)
    return records, reasons


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_writes_the_kept_articles_with_newspaper_and_edition(tmp_path: Path) -> None:
    records, reasons = write_inputs(tmp_path)
    counts = processed.build(records, reasons, tmp_path / "clean", batch_size=3)
    articles = read_csv(tmp_path / "clean" / "articles.csv")
    assert [a["doc_id"] for a in articles] == ["100", "102"]
    assert articles[0]["newspaper"] == "New York Times"
    assert articles[0]["edition"] == "print"
    assert articles[1]["text"] == "Synthetic body 2."
    assert "is_footer" not in articles[0]
    assert counts == {"articles": 2, "authors": 2, "article_authors": 3, "author_candidates": 0}


def test_build_links_only_articles_and_authors_that_exist(tmp_path: Path) -> None:
    records, reasons = write_inputs(tmp_path)
    processed.build(records, reasons, tmp_path / "clean")
    out = tmp_path / "clean"
    articles = {a["doc_id"] for a in read_csv(out / "articles.csv")}
    people = {a["author_id"] for a in read_csv(out / "authors.csv")}
    links = read_csv(out / "article_authors.csv")
    assert {link["doc_id"] for link in links} == articles
    assert {link["author_id"] for link in links} == people
    assert (out / "author_names.csv").exists()
    assert (out / "author_candidates.csv").exists()
