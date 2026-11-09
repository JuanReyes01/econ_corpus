"""Tests for econ_corpus.review_cases, using made-up names only."""

from pathlib import Path

from econ_corpus import review, review_cases

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
