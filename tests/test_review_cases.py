"""Tests for econ_corpus.review_cases, using made-up names only."""

import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus import parse, processed, review, review_cases
from econ_corpus.reasons import write_reasons

HEADER = ["author_id_a", "name_a", "articles_a", "author_id_b", "name_b", "articles_b", "kind"]


def test_parts_with_a_family_name_of_two_words_are_ambiguous() -> None:
    bylines = ["Jane Doe, Springfield; Roe, Richard", "Doe Roe, Ann", "Jane Doe, Springfield"]
    assert review_cases.ambiguous_parts(bylines, set()) == {
        "Jane Doe, Springfield": 2,
        "Doe Roe, Ann": 1,
    }


def test_particles_and_recovered_names_are_not_ambiguous() -> None:
    bylines = ["Van Doe, Jane", "de la Doe, Jane", "Jane Doe. Springfield", "The Editorial Board"]
    assert review_cases.ambiguous_parts(bylines, set()) == {}


def test_names_with_a_place_or_publication_word_are_watched() -> None:
    bylines = ["Sun, Springfield", "Washington, Jane", "Doe, Jane", "Jane Park"]
    assert review_cases.watched_parts(bylines, set()) == {
        "Sun, Springfield": 1,
        "Washington, Jane": 1,
        "Jane Park": 1,
    }


def test_parts_already_decided_are_not_listed_again() -> None:
    decided = {"Doe Roe, Ann", "Sun, Springfield"}
    assert review_cases.ambiguous_parts(["Doe Roe, Ann"], decided) == {}
    assert review_cases.watched_parts(["Sun, Springfield"], decided) == {}


def test_pairs_to_review_are_unreviewed_with_enough_articles_on_both_sides() -> None:
    candidates = [
        [*HEADER, "review"],
        ["1", "Jane Doe", "5", "2", "Jane Q Doe", "2", "no_shared_newspaper", "not_reviewed"],
        ["3", "Ann Poe", "9", "4", "Ann Poh", "1", "one_letter_apart", "not_reviewed"],
        ["5", "Al Roe", "4", "6", "Al Rowe", "4", "one_letter_apart", "unsure"],
    ]
    assert review_cases.pairs_to_review(candidates, min_articles=2) == [candidates[1]]


def test_evidence_shows_newspapers_years_and_two_titles() -> None:
    articles = [("Example Daily", 2001, "First title"), ("Example Daily", 1999, "Second title")]
    articles.append(("Sample Times", None, "Third title"))
    assert review_cases.evidence(articles) == (
        "Example Daily:2/Sample Times:1 1999-2001 | First title // Second title"
    )


def test_decided_parts_are_all_the_parts_in_the_review_file(tmp_path: Path) -> None:
    path = tmp_path / "parts.csv"
    path.write_text('part,replacement,reason\n"Van Doe, Jane",KEEP,\n"Doe Roe, Ann",UNSURE,\n')
    assert review.decided_parts(path) == {"Van Doe, Jane", "Doe Roe, Ann"}
    assert review.decided_parts(tmp_path / "none.csv") == set()


def test_bylines_that_name_nobody_are_listed_unless_unsigned_or_decided() -> None:
    bylines = ["The Editorial Board; Anonymous", "doe, jane", "Doe, Jane", "The Editorial Board"]
    assert review_cases.rejected_parts(bylines, set()) == {
        "The Editorial Board": 2,
        "doe, jane": 1,
    }
    assert review_cases.rejected_parts(bylines, {"doe, jane"}) == {"The Editorial Board": 2}


# --- files --------------------------------------------------------------------------

NYT = "newyorktimes,lateedition(eastcoast);newyork,n.y."
BYLINES = [
    "Haywood, Alyssa",
    "Haywood, Alyssa",
    "Haywoode, Alyssa",
    "Haywoode, Alyssa",
    "Jane Doe, Springfield",
    "Washington, Jane",
    "The Editorial Board",
]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_writes_every_kind_of_case_with_its_evidence(tmp_path: Path) -> None:
    rows = []
    for i, byline in enumerate([*BYLINES, None]):
        row = parse.empty_row("a.txt", i, is_footer=byline is None)
        if byline:
            row |= {"doc_id": 100 + i, "author": byline, "publication_key": NYT, "pub_year": 2020}
            row |= {"title": f"Title {i}", "text": "Synthetic body.", "has_body": True}
        rows.append(row)
    records, reasons = tmp_path / "records.parquet", tmp_path / "exclusions.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    codes = ["kept"] * 6 + ["no_person_author", "file_footer"]
    write_reasons(pq.read_table(records), codes, reasons)
    clean, review_dir = tmp_path / "clean", tmp_path / "review"
    processed.build(records, reasons, clean)
    counts = review_cases.build(records, reasons, clean, review_dir)
    assert counts == {
        "parts_to_review": 1,
        "names_to_review": 1,
        "rejected_to_review": 1,
        "pairs_to_review": 1,
        "merged_to_review": 0,
    }
    cases = review_dir / "cases"
    assert [r["part"] for r in read(cases / "parts_to_review.csv")] == ["Jane Doe, Springfield"]
    assert [r["part"] for r in read(cases / "names_to_review.csv")] == ["Washington, Jane"]
    assert read(cases / "rejected_to_review.csv") == [
        {"part": "The Editorial Board", "times": "1"}
    ]
    pair = read(cases / "pairs_to_review.csv")[0]
    assert (pair["kind"], pair["key_a"], pair["key_b"]) == (
        "one_letter_apart",
        "alyssahaywood",
        "alyssahaywoode",
    )
    assert (pair["name_a"], pair["articles_a"]) == ("Alyssa Haywood", "2")
    assert pair["evidence_a"] == "New York Times:2 2020-2020 | Title 0 // Title 1"
    assert pair["evidence_b"] == "New York Times:2 2020-2020 | Title 2 // Title 3"


def test_names_of_four_or_more_words_are_watched() -> None:
    bylines = ["Jane Mary Ann Doe", "Doe, Jane Mary Ann", "Jane Mary Doe", "Jane Doe Jr"]
    assert review_cases.watched_parts(bylines, set()) == {
        "Jane Mary Ann Doe": 1,
        "Doe, Jane Mary Ann": 1,
    }


def test_a_name_ending_in_a_town_is_watched() -> None:
    assert review_cases.watched_parts(["Jane Doe Syosset"], set()) == {"Jane Doe Syosset": 1}


NAMES = [
    ["author_id", "name", "name_key", "articles", "rule"],
    ["1", "James Doe", "jamesdoe", "40", "main"],
    ["1", "James Doe Jr", "jamesdoejr", "21", "shared_newspaper"],
    ["2", "John Roe Jr", "johnroejr", "30", "main"],
    ["2", "John Roe", "johnroe", "2", "shared_newspaper"],
    ["3", "Ann Poe", "annpoe", "9", "main"],
    ["3", "Ann Q Poe", "annqpoe", "9", "shared_newspaper"],
]


def test_merged_names_with_and_without_a_suffix_are_listed_when_both_are_frequent() -> None:
    assert review_cases.suffix_merges(NAMES, set(), min_articles=3) == [
        ["key_a", "name_a", "articles_a", "key_b", "name_b", "articles_b"],
        ["jamesdoe", "James Doe", "40", "jamesdoejr", "James Doe Jr", "21"],
    ]


def test_suffix_merges_already_decided_are_not_listed_again() -> None:
    decided = {("jamesdoe", "jamesdoejr")}
    assert review_cases.suffix_merges(NAMES, decided, min_articles=3)[1:] == []


def test_build_refuses_tables_built_before_the_review_files_changed(tmp_path: Path) -> None:
    rows = [parse.empty_row("a.txt", 0, is_footer=False)]
    rows[0] |= {"doc_id": 100, "author": "Doe, Jane", "publication_key": NYT, "pub_year": 2020}
    rows[0] |= {"title": "Title", "text": "Synthetic body.", "has_body": True}
    records, reasons = tmp_path / "records.parquet", tmp_path / "exclusions.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    write_reasons(pq.read_table(records), ["kept"], reasons)
    clean, review_dir = tmp_path / "clean", tmp_path / "review"
    review_dir.mkdir()
    processed.build(records, reasons, clean, review_dir=review_dir)
    (review_dir / "author_pairs.csv").write_text(
        "key_a,key_b,decision,reason\njanedoe,janeqdoe,same,\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="processed"):
        review_cases.build(records, reasons, clean, review_dir)


def test_names_read_by_moving_pieces_around_are_watched() -> None:
    bylines = ["Sen, Jane Doe", "Doe, Jane Roe and Ann", "Doe, Jane"]
    assert set(review_cases.watched_parts(bylines, set())) == {
        "Sen, Jane Doe",
        "Doe, Jane Roe and Ann",
    }


def test_build_lists_the_unread_parts_of_kept_articles_too(tmp_path: Path) -> None:
    rows = [parse.empty_row("a.txt", 0, is_footer=False)]
    rows[0] |= {"doc_id": 100, "publication_key": NYT, "pub_year": 2020}
    rows[0] |= {"author": "Doe, Jane; The Example Board", "title": "Title", "has_body": True}
    records, reasons = tmp_path / "records.parquet", tmp_path / "exclusions.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    write_reasons(pq.read_table(records), ["kept"], reasons)
    clean, review_dir = tmp_path / "clean", tmp_path / "review"
    processed.build(records, reasons, clean)
    assert review_cases.build(records, reasons, clean, review_dir)["rejected_to_review"] == 1
    assert read(review_dir / "cases" / "rejected_to_review.csv") == [
        {"part": "The Example Board", "times": "1"}
    ]


@pytest.mark.parametrize("part", ["Doe, Jane e", "DOE, BYJANE", "Doe, Jan e"])
def test_names_that_may_be_damaged_are_watched(part: str) -> None:
    assert review_cases.watched_parts([part], set()) == {part: 1}


def test_ordinary_names_are_not_watched() -> None:
    plain = [
        "Doe, Jane Q.",
        "J.Q. Doe",
        "Doe, Byron",
        "BYDOE, JANE",
        "Jane Q.Doe",
        "JANE DOE.Jane Doe is a teacher.",
    ]
    assert review_cases.watched_parts(plain, set()) == {}
