"""Tests for econ_corpus.review, using made-up names only."""

from pathlib import Path

from econ_corpus import review


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_review_files_mean_no_decisions(tmp_path: Path) -> None:
    assert review.load_parts(tmp_path / "none.csv") == {}
    assert review.load_pairs(tmp_path / "none.csv") == {}


def test_parts_give_the_corrected_byline_and_nobody_is_empty(tmp_path: Path) -> None:
    path = write(
        tmp_path / "parts.csv",
        "part,replacement,reason\n"
        '"Jane Doe, Springfield","Doe, Jane",town\n'
        '"Jane Doe, Richard Roe","Doe, Jane; Roe, Richard",two people\n'
        '"Example Board, The",NOBODY,institution\n',
    )
    assert review.load_parts(path) == {
        "Jane Doe, Springfield": "Doe, Jane",
        "Jane Doe, Richard Roe": "Doe, Jane; Roe, Richard",
        "Example Board, The": "",
    }


def test_parts_left_as_read_or_undecided_are_not_corrections(tmp_path: Path) -> None:
    path = write(
        tmp_path / "parts.csv",
        'part,replacement,reason\n"Van Doe, Jane",KEEP,double surname\n"Doe Roe, Jane",UNSURE,\n',
    )
    assert review.load_parts(path) == {}


def test_pairs_are_keyed_in_sorted_order_with_their_decision(tmp_path: Path) -> None:
    path = write(
        tmp_path / "pairs.csv",
        "key_a,key_b,decision,reason\njaneqdoe,janedoe,same,typo\nannpoe,annpoh,different,\n"
        "richardroe,richardrowe,unsure,\n",
    )
    assert review.load_pairs(path) == {
        ("janedoe", "janeqdoe"): "same",
        ("annpoe", "annpoh"): "different",
        ("richardroe", "richardrowe"): "unsure",
    }
