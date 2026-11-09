"""Tests for econ_corpus.names.identity, using made-up names only."""

from econ_corpus.names import authors, identity, lookalikes
from econ_corpus.names.identity import Seen

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
    assert lookalikes.candidates(names, identity.resolve(names)) == [
        ("janedoe", "janeqdoe", "no_shared_newspaper")
    ]


def test_contradicting_variants_are_candidates() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2), ("Doe, Jane R", {A}, 4))
    pairs = lookalikes.candidates(names, identity.resolve(names))
    assert pairs == [
        ("janedoe", "janeqdoe", "conflicting_names"),
        ("janedoe", "janerdoe", "conflicting_names"),
        ("janeqdoe", "janerdoe", "conflicting_names"),
    ]


def test_names_one_letter_apart_in_the_same_newspaper_are_candidates() -> None:
    names = seen(("Doewood, Marta", {A}, 1), ("Doewoode, Marta", {A}, 11))
    assert lookalikes.candidates(names, identity.resolve(names)) == [
        ("martadoewood", "martadoewoode", "one_letter_apart")
    ]


def test_one_changed_letter_counts_as_one_letter_apart() -> None:
    names = seen(("Morrison, Jonah", {A}, 1), ("Morrison, Jonas", {A}, 1))
    assert [kind for _, _, kind in lookalikes.candidates(names, identity.resolve(names))] == [
        "one_letter_apart"
    ]


def test_names_one_letter_apart_in_different_newspapers_are_not_candidates() -> None:
    names = seen(("Doewood, Marta", {A}, 1), ("Doewoode, Marta", {B}, 11))
    assert lookalikes.candidates(names, identity.resolve(names)) == []


def test_short_names_one_letter_apart_are_not_candidates() -> None:
    names = seen(("Li, Bo", {A}, 1), ("Li, Bob", {A}, 1))
    assert lookalikes.candidates(names, identity.resolve(names)) == []


def test_merged_variants_are_not_candidates() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2))
    assert lookalikes.candidates(names, identity.resolve(names)) == []


# --- decisions from the manual review ----------------------------------------------


def test_a_pair_reviewed_as_the_same_person_is_merged() -> None:
    names = seen(("Doewood, Marta", {A}, 1), ("Doewoode, Marta", {A}, 11))
    resolved = identity.resolve(names, same=[("martadoewood", "martadoewoode")])
    assert set(resolved.values()) == {"martadoewoode"}
    assert lookalikes.candidates(names, resolved) == []


def test_a_reviewed_pair_takes_the_variants_already_merged_with_it() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2), ("Dow, Jane", {A}, 3))
    resolved = identity.resolve(names, same=[("janeqdoe", "janedow")])
    assert set(resolved.values()) == {"janedoe"}


def test_reviewed_pairs_with_unknown_keys_are_ignored() -> None:
    names = seen(("Doe, Jane", {A}, 5))
    assert identity.resolve(names, same=[("janedoe", "nobodyhere")]) == {"janedoe": "janedoe"}


def test_two_edits_that_share_a_shorter_spelling_are_not_one_letter_apart() -> None:
    # Both keys lose a letter to give 'marklevin', but one edit does not turn one into the other.
    names = seen(("Levine, Mark", {A}, 3), ("Levin, Mark H", {A}, 3))
    assert lookalikes.candidates(names, identity.resolve(names)) == []


def test_two_swapped_letters_count_as_one_letter_apart() -> None:
    names = seen(("Schanberg, Sydney", {A}, 9), ("Scahnberg, Sydney", {A}, 1))
    assert [kind for _, _, kind in lookalikes.candidates(names, identity.resolve(names))] == [
        "one_letter_apart"
    ]


def test_a_pair_reviewed_as_different_is_not_merged_by_the_rule() -> None:
    names = seen(("Doe, Jane", {A}, 50), ("Doe, Jane Q", {A}, 2))
    resolved = identity.resolve(names, apart=[("janeqdoe", "janedoe")])
    assert resolved == {"janedoe": "janedoe", "janeqdoe": "janeqdoe"}
    assert lookalikes.candidates(names, resolved) == [("janedoe", "janeqdoe", "apart_by_review")]


def test_a_pair_kept_apart_also_stops_the_variants_linked_through_it() -> None:
    names = seen(("Doe, Jane", {A}, 5), ("Doe, Jane Q", {A, B}, 9), ("Doe, Jane Quinn", {B}, 1))
    resolved = identity.resolve(names, apart=[("janedoe", "janequinndoe")])
    assert resolved == {k: k for k in names}


# --- found in the audit ------------------------------------------------------------


def name(written: str) -> authors.Name:
    parsed = authors.parse_name(written)
    assert parsed is not None
    return parsed


def test_middle_names_are_compared_word_by_word() -> None:
    assert identity.compatible(name("Jane A Doe"), name("Jane Ann Doe"))
    assert identity.compatible(name("Jane Ann Marie Doe"), name("Jane Ann Doe"))
    assert identity.compatible(name("Jane A M Doe"), name("Jane Ann Doe"))
    assert not identity.compatible(name("Jane Ann Doe"), name("Jane Anne Doe"))
    assert not identity.compatible(name("Jane Al Doe"), name("Jane Alan Doe"))


def test_initials_written_apart_or_together_are_one_first_name() -> None:
    names = seen(("Doe, E J", {A}, 3), ("Doe, EJ, Jr", {A}, 30))
    assert set(identity.resolve(names).values()) == {"ejdoejr"}


def test_a_nickname_and_the_full_first_name_in_one_newspaper_are_candidates() -> None:
    names = seen(("Doe, Joe", {A}, 9), ("Doe, Joseph R, Jr", {A}, 5), ("Doe, Tim", {A}, 2))
    names |= seen(("Doe, Timothy", {A}, 2))
    pairs = lookalikes.candidates(names, identity.resolve(names))
    assert ("joedoe", "josephrdoejr", "nickname") in pairs
    assert ("timdoe", "timothydoe", "nickname") in pairs
    assert len(pairs) == 2


def test_nicknames_need_compatible_names_but_not_a_shared_newspaper() -> None:
    apart = seen(("Doe, Joe", {A}, 9), ("Doe, Joseph", {B}, 5))
    assert lookalikes.candidates(apart, identity.resolve(apart)) == [
        ("joedoe", "josephdoe", "nickname")
    ]
    clash = seen(("Doe, Joe Q", {A}, 9), ("Doe, Joseph R", {A}, 5))
    assert lookalikes.candidates(clash, identity.resolve(clash)) == []


def test_a_name_seen_with_given_and_family_swapped_is_a_candidate() -> None:
    names = seen(("Hockdoe, Lee", {A}, 300), ("Lee, Hockdoe", {A}, 40))
    assert lookalikes.candidates(names, identity.resolve(names)) == [
        ("hockdoelee", "leehockdoe", "swapped_names")
    ]


def test_an_initial_and_a_first_name_it_starts_are_candidates() -> None:
    names = seen(("Doe, J", {A}, 3), ("Doe, Jane", {A}, 5), ("Roe, Ann", {A}, 5))
    pairs = lookalikes.candidates(names, identity.resolve(names))
    assert pairs == [("janedoe", "jdoe", "nickname")]


def test_an_initial_before_a_full_given_name_is_not_a_short_form() -> None:
    names = seen(("Doe, J Brad", {A}, 3), ("Doe, Jane", {A}, 5))
    assert lookalikes.candidates(names, identity.resolve(names)) == []


def test_initials_and_the_given_names_they_stand_for_are_candidates() -> None:
    names = seen(("Doe, J Q", {A}, 1), ("Doe, Jane Q", {A}, 30), ("Doe, John Quincy", {B}, 2))
    pairs = {(a, b) for a, b, kind in lookalikes.candidates(names, identity.resolve(names))}
    assert ("janeqdoe", "jqdoe") in pairs
    assert ("johnquincydoe", "jqdoe") in pairs


def test_a_short_form_in_another_newspaper_is_a_candidate() -> None:
    names = seen(("Doe, Chuck", {A}, 21), ("Doe, Charles", {B}, 4))
    assert lookalikes.candidates(names, identity.resolve(names)) == [
        ("charlesdoe", "chuckdoe", "nickname")
    ]
