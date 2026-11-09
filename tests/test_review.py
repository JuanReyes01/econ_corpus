"""Tests for econ_corpus.names.review, using made-up names only."""

from pathlib import Path

import pytest

from econ_corpus.names import bylines, review


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


def test_markers_are_read_whatever_their_case(tmp_path: Path) -> None:
    path = write(
        tmp_path / "parts.csv",
        'part,replacement,reason\n"Van Doe, Jane",keep,\n"Doe Roe, Jane",Unsure,\n'
        '"Example Board, The",nobody,\n',
    )
    assert review.load_parts(path) == {"Example Board, The": ""}


def test_a_replacement_that_is_not_a_readable_byline_is_refused(tmp_path: Path) -> None:
    path = write(
        tmp_path / "parts.csv",
        'part,replacement,reason\n"Jane Doe, Springfield",ask the editor,\n',
    )
    with pytest.raises(ValueError, match="Jane Doe, Springfield"):
        review.load_parts(path)


def test_verdicts_are_normalised_and_unknown_ones_refused(tmp_path: Path) -> None:
    good = write(tmp_path / "pairs.csv", "key_a,key_b,decision,reason\njanedoe,janeqdoe, Same ,\n")
    assert review.load_pairs(good) == {("janedoe", "janeqdoe"): "same"}
    bad = write(tmp_path / "bad.csv", "key_a,key_b,decision,reason\njanedoe,janeqdoe,maybe,\n")
    with pytest.raises(ValueError, match="maybe"):
        review.load_pairs(bad)


def test_a_part_or_a_pair_listed_twice_is_refused(tmp_path: Path) -> None:
    text = 'part,replacement,reason\n"Jane Doe, Springfield","Doe, Jane",\n'
    parts = write(tmp_path / "parts.csv", text + '"Jane Doe, Springfield",KEEP,\n')
    with pytest.raises(ValueError, match="twice"):
        review.load_parts(parts)
    pairs = write(
        tmp_path / "pairs.csv",
        "key_a,key_b,decision,reason\njanedoe,janeqdoe,same,\njaneqdoe,janedoe,different,\n",
    )
    with pytest.raises(ValueError, match="twice"):
        review.load_pairs(pairs)


def test_fingerprint_depends_on_the_corrections_not_on_their_order() -> None:
    one = {"Jane Doe, Springfield": "Doe, Jane", "Example Board, The": ""}
    same = dict(reversed(one.items()))
    assert review.fingerprint(one) == review.fingerprint(same)
    assert review.fingerprint(one) != review.fingerprint({**one, "Example Board, The": "Doe, Al"})
    assert review.fingerprint({}) != review.fingerprint(one)


def test_an_empty_replacement_counts_as_kept_as_read() -> None:
    counts = review.outcome_counts([{"replacement": ""}, {"replacement": "Doe, Jane"}], [])
    assert (counts["n_parts_keep"], counts["n_parts_corrected"]) == (1, 1)


def test_the_review_folder_must_exist_even_if_empty(tmp_path: Path) -> None:
    assert review.folder(tmp_path) == tmp_path
    with pytest.raises(FileNotFoundError, match="review"):
        review.folder(tmp_path / "missing")


@pytest.mark.parametrize("bad", ["Doe, -", "-, Jane", "Doe, 12"])
def test_a_correction_without_letters_on_both_sides_is_refused(tmp_path: Path, bad: str) -> None:
    path = write(
        tmp_path / "parts.csv", f'part,replacement,reason\n"Jane Doe, Springfield","{bad}",\n'
    )
    with pytest.raises(ValueError, match="readable"):
        review.load_parts(path)


def test_a_review_folder_with_only_one_of_its_files_is_refused(tmp_path: Path) -> None:
    write(tmp_path / "byline_parts.csv", "part,replacement,reason\n")
    with pytest.raises(FileNotFoundError, match="author_pairs"):
        review.folder(tmp_path)
    write(tmp_path / "author_pairs.csv", "key_a,key_b,decision,reason\n")
    assert review.folder(tmp_path) == tmp_path


@pytest.mark.parametrize("part", ["Jane Doe ", " Jane Doe", "Doe, Jane; Roe, Ann"])
def test_a_part_that_no_byline_can_produce_is_refused(tmp_path: Path, part: str) -> None:
    path = write(tmp_path / "parts.csv", f'part,replacement,reason\n"{part}",NOBODY,\n')
    with pytest.raises(ValueError, match="never match"):
        review.load_parts(path)


def test_a_folder_with_only_the_case_lists_is_still_no_review(tmp_path: Path) -> None:
    (tmp_path / "cases").mkdir()
    (tmp_path / "cases" / "pairs_to_review.csv").write_text("kind\n", encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    assert review.folder(tmp_path) == tmp_path


# --- production credits ------------------------------------------------------------


def test_a_part_marked_credit_is_kept_as_a_marker_whatever_its_case(tmp_path: Path) -> None:
    path = write(
        tmp_path / "parts.csv",
        'part,replacement,reason\n"Roe, Richard",CREDIT,producer\n"Poe, Ann",credit,\n',
    )
    assert review.load_parts(path) == {"Roe, Richard": bylines.CREDIT, "Poe, Ann": bylines.CREDIT}


def test_credits_are_counted_apart_from_corrections() -> None:
    parts = [{"replacement": "CREDIT"}, {"replacement": "Doe, Jane"}, {"replacement": "NOBODY"}]
    counts = review.outcome_counts(parts, [])
    assert (counts["n_parts_credit"], counts["n_parts_corrected"]) == (1, 1)
