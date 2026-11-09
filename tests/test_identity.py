"""Tests for econ_corpus.identity, using made-up names only."""

from econ_corpus import authors, identity
from econ_corpus.identity import Seen

A, B = "Example Daily", "Sample Times"


def seen(*rows: tuple[str, set[str], int]) -> dict[str, Seen]:
    """Build the observed names from (name as written, newspapers, articles)."""
    out = {}
    for written, papers, articles in rows:
        name = authors.parse_name(written)
        assert name is not None
        out[authors.name_key(name)] = Seen(name, frozenset(papers), articles)
    return out


# --- when two names are compatible -------------------------------------------------


def test_missing_middle_name_or_initial_of_it_is_compatible() -> None:
    full, initial, bare = (
        authors.parse_name(p) for p in ("Jane Quinn Doe", "Jane Q Doe", "Jane Doe")
    )
    assert identity.compatible(full, initial)
    assert identity.compatible(initial, bare)
    assert identity.compatible(full, bare)


def test_different_middle_names_are_not_compatible() -> None:
    assert not identity.compatible(
        authors.parse_name("Jane Q Doe"), authors.parse_name("Jane R Doe")
    )


def test_missing_suffix_is_compatible_but_two_suffixes_are_not() -> None:
    plain, junior, third = (
        authors.parse_name(p) for p in ("John Doe", "John Doe Jr", "John Doe III")
    )
    assert identity.compatible(plain, junior)
    assert not identity.compatible(junior, third)


# --- which names are one author ----------------------------------------------------


def test_a_name_seen_alone_is_its_own_author() -> None:
    assert identity.resolve(seen(("Doe, Jane", {A}, 3))) == {"janedoe": "janedoe"}


def test_variants_that_share_a_newspaper_are_one_author_named_by_the_commonest() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A, B}, 2))
    assert identity.resolve(names) == {"janedoe": "janedoe", "janeqdoe": "janedoe"}


def test_variants_without_a_shared_newspaper_stay_apart() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {B}, 2))
    assert identity.resolve(names) == {"janedoe": "janedoe", "janeqdoe": "janeqdoe"}


def test_a_contradiction_in_the_group_stops_every_merge() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2), ("Doe, Jane R", {A}, 4))
    resolved = identity.resolve(names)
    assert resolved == {k: k for k in names}


def test_suffix_missing_in_one_variant_is_one_author() -> None:
    names = seen(("Doe, John", {A}, 2), ("Doe, John, Jr", {A}, 40))
    assert set(identity.resolve(names).values()) == {"johndoejr"}


def test_newspapers_link_variants_in_a_chain() -> None:
    names = seen(("Doe, Jane", {A}, 5), ("Doe, Jane Q", {A, B}, 9), ("Doe, Jane Quinn", {B}, 1))
    assert set(identity.resolve(names).values()) == {"janeqdoe"}


def test_different_first_names_or_families_are_never_merged() -> None:
    names = seen(("Doe, Jane", {A}, 5), ("Doe, Joan", {A}, 5), ("Roe, Jane", {A}, 5))
    assert identity.resolve(names) == {k: k for k in names}


def test_ties_are_named_by_the_longest_name() -> None:
    names = seen(("Doe, Jane", {A}, 5), ("Doe, Jane Q", {A}, 5))
    assert set(identity.resolve(names).values()) == {"janeqdoe"}


# --- pairs left for review ---------------------------------------------------------


def test_compatible_variants_without_a_shared_newspaper_are_candidates() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {B}, 2))
    assert identity.candidates(names, identity.resolve(names)) == [
        ("janedoe", "janeqdoe", "no_shared_newspaper")
    ]


def test_contradicting_variants_are_candidates() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2), ("Doe, Jane R", {A}, 4))
    pairs = identity.candidates(names, identity.resolve(names))
    assert pairs == [
        ("janedoe", "janeqdoe", "conflicting_names"),
        ("janedoe", "janerdoe", "conflicting_names"),
        ("janeqdoe", "janerdoe", "conflicting_names"),
    ]


def test_names_one_letter_apart_in_the_same_newspaper_are_candidates() -> None:
    names = seen(("Haywood, Alyssa", {A}, 1), ("Haywoode, Alyssa", {A}, 11))
    assert identity.candidates(names, identity.resolve(names)) == [
        ("alyssahaywood", "alyssahaywoode", "one_letter_apart")
    ]


def test_one_changed_letter_counts_as_one_letter_apart() -> None:
    names = seen(("Morrison, Jonah", {A}, 1), ("Morrison, Jonas", {A}, 1))
    assert [kind for _, _, kind in identity.candidates(names, identity.resolve(names))] == [
        "one_letter_apart"
    ]


def test_names_one_letter_apart_in_different_newspapers_are_not_candidates() -> None:
    names = seen(("Haywood, Alyssa", {A}, 1), ("Haywoode, Alyssa", {B}, 11))
    assert identity.candidates(names, identity.resolve(names)) == []


def test_short_names_one_letter_apart_are_not_candidates() -> None:
    names = seen(("Li, Bo", {A}, 1), ("Li, Bob", {A}, 1))
    assert identity.candidates(names, identity.resolve(names)) == []


def test_merged_variants_are_not_candidates() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2))
    assert identity.candidates(names, identity.resolve(names)) == []
