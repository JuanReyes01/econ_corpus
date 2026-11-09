"""Tests for econ_corpus.processed on tiny synthetic tables (made-up names, no article text)."""

import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus import manifest, parse, processed, review
from econ_corpus.reasons import write_reasons

A, B = "Example Daily", "Sample Times"
NYT = "newyorktimes,lateedition(eastcoast);newyork,n.y."


def tables_for(
    *rows: tuple[int, str, str],
    corrections: dict[str, str] | None = None,
    decisions: dict[tuple[str, str], str] | None = None,
) -> dict[str, list[list[str]]]:
    """Build the author tables from (doc id, byline, newspaper) rows."""
    ids, bylines, papers = zip(*rows, strict=True)
    return processed.author_tables(
        list(ids), list(bylines), list(papers), corrections or {}, decisions or {}
    )


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
        [
            "author_id_a",
            "name_a",
            "articles_a",
            "author_id_b",
            "name_b",
            "articles_b",
            "kind",
            "review",
        ],
        ["1", "Jane Doe", "2", "2", "Jane Q Doe", "1", "no_shared_newspaper", "not_reviewed"],
    ]


# --- manual review ------------------------------------------------------------------

PAIR = ("janedoe", "janeqdoe")
APART = ((10, "Doe, Jane", A), (11, "Doe, Jane", A), (12, "Doe, Jane Q", B))


def test_a_pair_reviewed_as_the_same_is_one_author_with_the_rule_recorded() -> None:
    tables = tables_for(*APART, decisions={PAIR: "same"})
    assert body(tables["authors"]) == [["1", "Jane Doe", "3", "2"]]
    assert [row[4] for row in body(tables["author_names"])] == ["main", "manual_review"]
    assert body(tables["author_candidates"]) == []


def test_a_pair_reviewed_as_different_or_unsure_stays_apart_and_says_so() -> None:
    for decision in ("different", "unsure"):
        tables = tables_for(*APART, decisions={PAIR: decision})
        assert len(body(tables["authors"])) == 2
        assert [row[-1] for row in body(tables["author_candidates"])] == [decision]


def test_a_corrected_part_is_linked_as_manual_review() -> None:
    corrections = {"Jane Doe, Springfield": "Doe, Jane"}
    tables = tables_for((10, "Jane Doe, Springfield", A), corrections=corrections)
    assert body(tables["authors"]) == [["1", "Jane Doe", "1", "1"]]
    assert body(tables["article_authors"]) == [["10", "1", "1", "manual_review"]]


HAYWOOD = (
    (10, "Doewood, Marta", A),
    (11, "Doewood, Marta Q", A),
    (12, "Doewoode, Marta", A),
    (13, "Doewoode, Marta", A),
)


def test_a_pair_judged_different_that_ends_merged_is_refused() -> None:
    rows = ((10, "Doewood, Marta", A), (11, "Doewoode, Marta", A), (12, "Doewooden, Marta", A))
    decisions = {
        ("martadoewood", "martadoewoode"): "same",
        ("martadoewoode", "martadoewooden"): "same",
        ("martadoewood", "martadoewooden"): "different",
    }
    with pytest.raises(ValueError, match="martadoewooden"):
        tables_for(*rows, decisions=decisions)


def test_two_verdicts_on_one_pair_of_authors_keep_the_most_cautious() -> None:
    decisions = {
        ("martadoewood", "martadoewoode"): "unsure",
        ("martadoewoode", "martaqdoewood"): "different",
    }
    for order in (decisions, dict(reversed(decisions.items()))):
        tables = tables_for(*HAYWOOD, decisions=order)
        assert [row[-1] for row in body(tables["author_candidates"])] == ["different"]


SHARED = ((10, "Doe, Jane", A), (11, "Doe, Jane", A), (12, "Doe, Jane Q", A))


def test_a_pair_judged_different_stays_apart_even_if_the_rule_would_merge_it() -> None:
    tables = tables_for(*SHARED, decisions={PAIR: "different"})
    assert len(body(tables["authors"])) == 2
    assert [row[-2:] for row in body(tables["author_candidates"])] == [
        ["apart_by_review", "different"]
    ]


def test_the_rule_decides_a_pair_the_review_was_unsure_about() -> None:
    tables = tables_for(*SHARED, decisions={PAIR: "unsure"})
    assert body(tables["authors"]) == [["1", "Jane Doe", "3", "2"]]
    assert body(tables["author_candidates"]) == []


def test_a_variant_joined_only_by_the_review_is_not_credited_to_the_rule() -> None:
    rows = ((10, "Doe, Jane", A), (11, "Doe, Jane Q", A), (12, "Doe, Jane Quinn", A))
    rows += ((13, "Doe, Jane Quinn", A),)
    decisions = {("janedoe", "janequinndoe"): "different", ("janeqdoe", "janequinndoe"): "same"}
    tables = tables_for(*rows, decisions=decisions)
    rules = {row[2]: row[4] for row in body(tables["author_names"])}
    assert rules == {"janedoe": "main", "janequinndoe": "main", "janeqdoe": "manual_review"}


# --- files --------------------------------------------------------------------------


KEYS = {"source_file": ["a.txt"] * 4, "record_index": [0, 1, 2, 3]}


def write_inputs(tmp_path: Path, corrections: dict[str, str] | None = None) -> tuple[Path, Path]:
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
    stamp = {"byline_parts": review.fingerprint(corrections or {})}
    write_reasons(pq.read_table(records), codes, reasons, stamp, row_group_size=3)
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


def test_build_applies_the_review_files_when_they_exist(tmp_path: Path) -> None:
    records, reasons = write_inputs(tmp_path, {"Roe, Richard": "Rowe, Richard"})
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    (review_dir / "byline_parts.csv").write_text(
        'part,replacement,reason\n"Roe, Richard","Rowe, Richard",spelling\n', encoding="utf-8"
    )
    processed.build(records, reasons, tmp_path / "clean", review_dir=review_dir)
    names = {a["name"] for a in read_csv(tmp_path / "clean" / "authors.csv")}
    assert names == {"Jane Doe", "Richard Rowe"}


def test_build_refuses_reasons_that_keep_an_article_without_a_person(tmp_path: Path) -> None:
    records, _ = write_inputs(tmp_path)
    stale = tmp_path / "stale.parquet"
    write_reasons(pq.read_table(records), ["kept", "kept", "kept", "file_footer"], stale)
    with pytest.raises(ValueError, match="exclusions"):
        processed.build(records, stale, tmp_path / "clean")


def test_build_refuses_reasons_that_belong_to_other_rows(tmp_path: Path) -> None:
    records, _ = write_inputs(tmp_path)
    other = tmp_path / "other.parquet"
    keys = {"source_file": ["a.txt"] * 4, "record_index": [1, 0, 2, 3]}
    codes = ["kept", "no_person_author", "kept", "file_footer"]
    pq.write_table(pa.table({**keys, "reason": codes}), other)
    with pytest.raises(ValueError, match="rows"):
        processed.build(records, other, tmp_path / "clean")


def test_build_refuses_a_kept_article_without_a_proquest_id(tmp_path: Path) -> None:
    rows = [parse.empty_row("a.txt", 0, is_footer=False)]
    rows[0] |= {"author": "Doe, Jane", "publication_key": NYT, "has_body": True}
    records = tmp_path / "records.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    reasons = tmp_path / "exclusions.parquet"
    write_reasons(pq.read_table(records), ["kept"], reasons)
    with pytest.raises(ValueError, match="ProQuest id"):
        processed.build(records, reasons, tmp_path / "clean")


def test_build_refuses_reasons_computed_with_other_review_files(tmp_path: Path) -> None:
    records, reasons = write_inputs(tmp_path)  # reasons computed without any review
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    (review_dir / "byline_parts.csv").write_text(
        'part,replacement,reason\n"Roe, Richard","Rowe, Richard",spelling\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="review"):
        processed.build(records, reasons, tmp_path / "clean", review_dir=review_dir)


def test_an_interrupted_build_leaves_no_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records, reasons = write_inputs(tmp_path)
    clean = tmp_path / "clean"
    processed.build(records, reasons, clean)
    assert (clean / "manifest.json").exists()

    def stop(*_: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(processed, "_write_articles", stop)
    with pytest.raises(KeyboardInterrupt):
        processed.build(records, reasons, clean)
    assert not (clean / "manifest.json").exists()


def test_the_manifest_refuses_a_table_that_was_cut(tmp_path: Path) -> None:
    records, reasons = write_inputs(tmp_path)
    clean = tmp_path / "clean"
    processed.build(records, reasons, clean)
    manifest.check(clean, records, reasons, None)
    articles = clean / "articles.csv"
    articles.write_text(articles.read_text(encoding="utf-8")[:-20], encoding="utf-8")
    with pytest.raises(ValueError, match=r"articles\.csv"):
        manifest.check(clean, records, reasons, None)


def test_the_manifest_refuses_a_table_changed_without_changing_its_size(tmp_path: Path) -> None:
    records, reasons = write_inputs(tmp_path)
    clean = tmp_path / "clean"
    processed.build(records, reasons, clean)
    authors = clean / "authors.csv"
    changed = authors.read_text(encoding="utf-8").replace("Jane", "Jone")
    authors.write_text(changed, encoding="utf-8")
    with pytest.raises(ValueError, match=r"authors\.csv"):
        manifest.check(clean, records, reasons, None)
