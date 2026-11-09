"""Tests for econ_corpus.clean.review_cases, using made-up names only."""

import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus.clean import author_cases, processed, review_cases
from econ_corpus.names import review
from econ_corpus.raw import parse
from econ_corpus.raw.reasons import write_reasons

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
    assert author_cases.pairs_to_review(candidates, min_articles=2) == [candidates[1]]


def test_evidence_shows_newspapers_years_and_two_titles() -> None:
    articles = [("Example Daily", 2001, "First title"), ("Example Daily", 1999, "Second title")]
    articles.append(("Sample Times", None, "Third title"))
    assert author_cases.evidence(articles) == (
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
    "Doewood, Marta",
    "Doewood, Marta",
    "Doewoode, Marta",
    "Doewoode, Marta",
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
        "distant_to_review": 0,
        "unused_parts": 0,
        "unused_pairs": 0,
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
        "martadoewood",
        "martadoewoode",
    )
    assert (pair["name_a"], pair["articles_a"]) == ("Marta Doewood", "2")
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
    assert author_cases.suffix_merges(NAMES, set(), min_articles=3) == [
        ["key_a", "name_a", "articles_a", "key_b", "name_b", "articles_b"],
        ["jamesdoe", "James Doe", "40", "jamesdoejr", "James Doe Jr", "21"],
    ]


def test_suffix_merges_already_decided_are_not_listed_again() -> None:
    decided = {("jamesdoe", "jamesdoejr")}
    assert author_cases.suffix_merges(NAMES, decided, min_articles=3)[1:] == []


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


def test_a_pair_with_one_frequent_author_is_reviewed_whatever_the_other_has() -> None:
    candidates = [
        [*HEADER, "review"],
        ["1", "Jane Doe", "900", "2", "Jane Deo", "1", "one_letter_apart", "not_reviewed"],
        ["3", "Ann Poe", "9", "4", "Ann Poh", "1", "one_letter_apart", "not_reviewed"],
    ]
    assert [row[1] for row in author_cases.pairs_to_review(candidates)] == ["Jane Doe"]


def test_decisions_that_apply_to_nothing_are_listed() -> None:
    bylines = ["Doe, Jane; The Example Board"]
    decided = {"The Example Board", "Roe, Ann", "Doe, Jane"}
    assert review_cases.unused_parts(bylines, decided) == ["Roe, Ann"]
    pairs = {("janedoe", "janeqdoe"), ("annroe", "annroh")}
    assert author_cases.unused_pairs(pairs, {"janedoe", "janeqdoe", "annroe"}) == [
        ("annroe", "annroh")
    ]


# --- variants of a name that are years apart ---------------------------------------

FAR = [
    ["author_id", "name", "name_key", "articles", "rule"],
    ["1", "Jane Doe", "janedoe", "3", "main"],
    ["1", "Jane Q Doe", "janeqdoe", "1", "shared_newspaper"],
    ["1", "Jane Quinn Doe", "janequinndoe", "1", "shared_newspaper"],
    ["1", "Jayne Doe", "jaynedoe", "1", "manual_review"],
    ["2", "Ann Poe", "annpoe", "2", "main"],
    ["2", "Ann R Poe", "annrpoe", "1", "shared_newspaper"],
    ["3", "Richard Roe", "richardroe", "1", "main"],
    ["4", "Tom Lee", "tomlee", "1", "main"],
    ["4", "Tom B Lee", "tomblee", "1", "shared_newspaper"],
    ["5", "Ann Lee", "annlee", "1", "main"],
    ["5", "Ann B Lee", "annblee", "1", "shared_newspaper"],
]
SIGNED = {
    "janedoe": [("Newsday", 1990, "First"), ("Newsday", 1992, "Second"), ("Newsday", None, "x")],
    "janeqdoe": [("Newsday", 2001, "Third")],
    "janequinndoe": [("Newsday", 1995, "Fourth")],
    "jaynedoe": [("Newsday", 2020, "Fifth")],
    "annpoe": [("Newsday", 2000, "Sixth"), ("Newsday", 2010, "Seventh")],
    "annrpoe": [("Newsday", 2005, "Eighth")],
    "richardroe": [("Newsday", 1980, "Ninth")],
    "tomlee": [("Newsday", 2000, "Tenth")],
    "tomblee": [("Newsday", 2004, "Eleventh")],
    "annlee": [("Newsday", 2005, "Twelfth")],
    "annblee": [("Newsday", 2000, "Thirteenth")],
}
FAR_HEADER = [
    "key_a", "name_a", "articles_a", "evidence_a",
    "key_b", "name_b", "articles_b", "evidence_b", "years_apart",
]  # fmt: skip


def far_pairs(decided: set[tuple[str, str]] = frozenset(), **gap: int) -> list[tuple[str, ...]]:
    table = author_cases.distant_merges(FAR, SIGNED, set(decided), **gap)
    return [(row[0], row[4], row[8]) for row in table[1:]]


def test_variants_of_an_author_with_years_between_them_are_listed_in_order() -> None:
    # Exactly five years are enough, four are not; 2005 falls inside 2000-2010.
    assert far_pairs() == [
        ("annblee", "annlee", "5"),
        ("janedoe", "janeqdoe", "9"),
        ("janedoe", "jaynedoe", "28"),
        ("janeqdoe", "janequinndoe", "6"),
        ("janeqdoe", "jaynedoe", "19"),
        ("janequinndoe", "jaynedoe", "25"),
    ]
    assert ("tomblee", "tomlee", "4") in far_pairs(min_gap=4)
    assert ("janedoe", "janequinndoe", "3") in far_pairs(min_gap=3)


def test_a_distant_merge_is_listed_with_the_evidence_of_each_variant() -> None:
    table = author_cases.distant_merges(FAR, SIGNED, set())
    assert table[0] == FAR_HEADER
    assert table[2] == [
        *("janedoe", "Jane Doe", "3", "Newsday:3 1990-1992 | First // Second"),
        *("janeqdoe", "Jane Q Doe", "1", "Newsday:1 2001-2001 | Third"),
        "9",
    ]


def test_a_variant_joined_by_the_review_is_compared_with_the_others_too() -> None:
    # Its verdict was on one pair; the other variants of the author were never set against it.
    assert sum("jaynedoe" in pair for pair in far_pairs()) == len(["jane", "janeq", "janequinn"])


def test_distant_merges_already_decided_are_not_listed_again() -> None:
    assert ("janedoe", "janeqdoe", "9") not in far_pairs({("janedoe", "janeqdoe")})
    assert len(far_pairs({("janedoe", "janeqdoe")})) == len(far_pairs()) - 1


def test_a_variant_with_no_dated_article_is_not_listed() -> None:
    undated = SIGNED | {"janeqdoe": [("Newsday", None, "Third")]}
    table = author_cases.distant_merges(FAR, undated, set())
    assert not any("janeqdoe" in row for row in table[1:])


def far_records(tmp_path: Path, signed: list[tuple[str, int]]) -> tuple[Path, Path]:
    rows = []
    for i, (byline, year) in enumerate(signed):
        row = parse.empty_row("a.txt", i, is_footer=False)
        row |= {"doc_id": 100 + i, "author": byline, "publication_key": NYT, "pub_year": year}
        rows.append(row | {"title": f"Title {i}", "text": "Synthetic body.", "has_body": True})
    records = tmp_path / "records.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    return records, tmp_path / "exclusions.parquet"


def test_build_lists_the_variants_of_an_author_that_are_years_apart(tmp_path: Path) -> None:
    signed = [("Doe, Jane", 1990), ("Doe, Jane Q", 2010), ("Roe, Richard", 2010)]
    records, reasons = far_records(tmp_path, signed)
    write_reasons(pq.read_table(records), ["kept"] * 3, reasons)
    clean, review_dir = tmp_path / "clean", tmp_path / "review"
    processed.build(records, reasons, clean)
    assert review_cases.build(records, reasons, clean, review_dir)["distant_to_review"] == 1
    (case,) = read(review_dir / "cases" / "distant_to_review.csv")
    assert (case["key_a"], case["key_b"], case["years_apart"]) == ("janedoe", "janeqdoe", "20")
    assert case["evidence_b"] == "New York Times:1 2010-2010 | Title 1"
    # Once the pair is judged, it is not listed again.
    (review_dir / "author_pairs.csv").write_text(
        "key_a,key_b,decision,reason\njaneqdoe,janedoe,unsure,\n", encoding="utf-8"
    )
    processed.build(records, reasons, clean, review_dir=review_dir)
    assert review_cases.build(records, reasons, clean, review_dir)["distant_to_review"] == 0


def test_build_reads_the_bylines_with_the_corrections_of_the_review(tmp_path: Path) -> None:
    records, reasons = far_records(
        tmp_path, [("Doe, Jane", 1990), ("Jane Q Doe, Springfield", 2010)]
    )
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    (review_dir / "byline_parts.csv").write_text(
        'part,replacement,reason\n"Jane Q Doe, Springfield","Doe, Jane Q",a town\n',
        encoding="utf-8",
    )
    corrections = review.load_parts(review_dir / "byline_parts.csv")
    stamps = {review.STAMP: review.fingerprint(corrections)}
    write_reasons(pq.read_table(records), ["kept"] * 2, reasons, stamps)
    clean = tmp_path / "clean"
    processed.build(records, reasons, clean, review_dir=review_dir)
    assert review_cases.build(records, reasons, clean, review_dir)["distant_to_review"] == 1
    (case,) = read(review_dir / "cases" / "distant_to_review.csv")
    assert (case["key_a"], case["key_b"]) == ("janedoe", "janeqdoe")
