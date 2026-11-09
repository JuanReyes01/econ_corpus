"""Tests for econ_corpus.authors, using made-up names only."""

import pytest

from econ_corpus import authors
from econ_corpus.authors import Name

# --- splitting a byline into parts -------------------------------------------------


def test_none_and_empty_bylines_have_no_parts() -> None:
    assert authors.split_authors(None) == []
    assert authors.split_authors("  ;  ") == []


def test_semicolon_separates_authors() -> None:
    assert authors.split_authors("Doe, Jane; Roe, Richard A") == ["Doe, Jane", "Roe, Richard A"]


def test_a_suffix_standing_alone_joins_the_name_before_it() -> None:
    assert authors.split_authors("Doe, John W; Jr.") == ["Doe, John W, Jr"]
    assert authors.split_authors("Doe, John W; Jr.; Roe, Ann") == ["Doe, John W, Jr", "Roe, Ann"]


def test_a_suffix_with_no_name_before_it_is_kept_as_written() -> None:
    assert authors.split_authors("Jr.") == ["Jr."]


@pytest.mark.parametrize("joiner", [" and ", " AND ", " And ", " & "])
def test_and_separates_names_written_without_commas(joiner: str) -> None:
    assert authors.split_authors(f"Jane Doe{joiner}Richard Roe") == ["Jane Doe", "Richard Roe"]


def test_and_inside_a_comma_form_is_not_a_separator() -> None:
    assert authors.split_authors("Doe, Jane and Co") == ["Doe, Jane and Co"]


@pytest.mark.parametrize("raw", ["By Jane Doe", "by Jane Doe", "BY Jane Doe"])
def test_leading_by_is_removed(raw: str) -> None:
    assert authors.split_authors(raw) == ["Jane Doe"]


def test_a_name_that_starts_with_by_letters_is_not_cut() -> None:
    assert authors.split_authors("Byron Doe") == ["Byron Doe"]


# --- reading one part as a person --------------------------------------------------


def test_last_comma_first_is_a_person() -> None:
    assert authors.parse_name("Doe, Jane Q") == Name("Jane Q", "Doe", "")


def test_two_word_family_name_before_the_comma() -> None:
    assert authors.parse_name("Van Doe, Jane") == Name("Jane", "Van Doe", "")


@pytest.mark.parametrize(
    ("part", "suffix"),
    [("Doe, John W, Jr", "Jr"), ("Doe, John W, JR.", "Jr"), ("Doe, John W, III", "III")],
)
def test_suffix_after_a_second_comma(part: str, suffix: str) -> None:
    assert authors.parse_name(part) == Name("John W", "Doe", suffix)


def test_natural_order_name_is_a_person() -> None:
    assert authors.parse_name("Jane Q. Doe") == Name("Jane Q.", "Doe", "")


def test_natural_order_keeps_particles_with_the_family_name() -> None:
    assert authors.parse_name("Jane Van Doe") == Name("Jane", "Van Doe", "")
    assert authors.parse_name("Jane Mary vanden Doe") == Name("Jane Mary", "vanden Doe", "")


def test_natural_order_suffix_is_read() -> None:
    assert authors.parse_name("John Doe Jr.") == Name("John", "Doe", "Jr")


@pytest.mark.parametrize(
    "part", ["Dr. Jane Doe", "Prof Jane Doe", "Doe, Dr Jane", "Doe, Sen. Jane"]
)
def test_honorifics_are_dropped(part: str) -> None:
    assert authors.parse_name(part) == Name("Jane", "Doe", "")


def test_initials_with_periods_are_accepted() -> None:
    assert authors.parse_name("J.Q.R. Doe") == Name("J.Q.R.", "Doe", "")
    assert authors.parse_name("Doe, J") == Name("J", "Doe", "")


@pytest.mark.parametrize(
    "part",
    [
        "Anonymous",
        "The Editorial Board",
        "Opinion contributor",
        "Example Daily Editorial Board",
        "Example Free Press",
        "Readers",
        "Doe",  # one word
        "Jr.",
        "Jane Doe11 Jane Doe",  # digits
        "Jane Doe is a member of the Example editorial board",  # a sentence
        "Jane Doe. Springfield",  # a word that ends a sentence
        "Jane Doe - Springfield",
        "a guest columnist",  # no capital letters
        ", Jane",  # empty family name
        "Jane Doe,",  # empty given name
        "Staff, Example Opinions",
        "Jane Doe, Example Staff",
        "Jane Q. Doe, MD",  # a degree, not a given name
        'Doe, Jane "JD"',
        "Jane Doe, Richard Roe and Ann Poe",
        "One Two Three Four Five Six",
    ],
)
def test_bylines_that_are_not_a_person_name_are_rejected(part: str) -> None:
    assert authors.parse_name(part) is None


def test_org_word_as_a_family_name_is_accepted_in_comma_form() -> None:
    assert authors.parse_name("Press, Jane") == Name("Jane", "Press", "")


# --- display name and key ----------------------------------------------------------


def test_display_puts_given_name_first_and_suffix_last() -> None:
    assert authors.display(Name("John W", "Doe", "Jr")) == "John W Doe Jr"


def test_display_fixes_names_written_in_capitals() -> None:
    assert authors.display(Name("JANE Q", "O'DOE-ROE", "")) == "Jane Q O'Doe-Roe"
    assert authors.display(Name("JANE", "del DOE", "")) == "Jane del Doe"
    assert authors.display(Name("J.Q.", "DOE", "")) == "J.Q. Doe"


def test_display_leaves_mixed_case_names_alone() -> None:
    assert authors.display(Name("Jane", "McDoe", "")) == "Jane McDoe"


@pytest.mark.parametrize(
    "part",
    [
        "Doe, Jane Q",
        "DOE, JANE Q",
        "Jane Q. Doe",
        "Doe, Jane Q.",
        "D oe, Jane Q",  # stray space, as ProQuest inserts in metadata
        "Dr. Jane Q Doe",
    ],
)
def test_key_is_the_same_for_spelling_variants_of_one_name(part: str) -> None:
    assert authors.name_key(authors.parse_name(part)) == "janeqdoe"


def test_key_joins_initials_however_they_are_spaced() -> None:
    keys = {
        authors.name_key(authors.parse_name(p))
        for p in ("Doe, EJ, Jr", "Doe, E J, Jr", "E.J. Doe Jr.")
    }
    assert keys == {"ejdoejr"}


def test_key_ignores_accents_and_curly_apostrophes() -> None:
    assert authors.name_key(Name("José", "O\u2019Doe", "")) == authors.name_key(
        Name("Jose", "O'Doe", "")
    )


def test_key_keeps_suffix_and_middle_name_apart() -> None:
    plain = authors.name_key(Name("John", "Doe", ""))
    assert authors.name_key(Name("John", "Doe", "Jr")) != plain
    assert authors.name_key(Name("John W", "Doe", "")) != plain


# --- people in a byline ------------------------------------------------------------


def test_people_returns_persons_in_order_and_drops_the_rest() -> None:
    raw = "Doe, Jane; The Editorial Board; Roe, Richard A"
    assert authors.people(raw) == [Name("Jane", "Doe", ""), Name("Richard A", "Roe", "")]


def test_people_lists_a_person_once_per_byline() -> None:
    assert authors.people("Doe, Jane; DOE, JANE") == [Name("Jane", "Doe", "")]


@pytest.mark.parametrize("raw", [None, "", "Anonymous", "The Editorial Board; Anonymous"])
def test_bylines_without_a_person_give_no_people(raw: str | None) -> None:
    assert authors.people(raw) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, False),
        ("", False),
        ("Anonymous", False),
        ("anonymous ", False),
        ("The Editorial Board", True),
        ("Doe, Jane", True),
    ],
)
def test_is_signed_tells_unsigned_from_any_other_byline(
    raw: str | None, *, expected: bool
) -> None:
    assert authors.is_signed(raw) is expected


# --- a full name followed by other text --------------------------------------------


@pytest.mark.parametrize(
    "part",
    [
        "Jane Doe. Springfield",
        "Jane Doe - Springfield",
        "Jane Doe, Springfield Heights. The writer is a teacher",
        "Jane Doe11 Jane Doe",
        "Jane Doe Jane Doe is a member of the Example editorial board",
        "JANE DOE. Jane Doe is a columnist",
        "Jane Doe is a member of the Example editorial board",
        "Jane Doe, a member of the Example editorial board",
        "Jane Doe, Example Staff",
        "Jane Doe's column appears regularly",
        "By Jane Doe. Jane Doe is a writer",
        "Jane Doe, (copyright) 1990, Example Syndicate",
        "Jane Doe writes a weekly column",
    ],
)
def test_a_full_name_followed_by_other_text_is_recovered(part: str) -> None:
    assert authors.parse_name(part) is None
    assert [authors.name_key(n) for n in authors.recover_names(part)] == ["janedoe"]


def test_recovered_name_keeps_middle_initial_and_suffix() -> None:
    assert authors.recover_names("Jane Q. Doe, MD") == [Name("Jane Q.", "Doe", "")]
    recovered = authors.recover_names("John W Doe Jr, President, Example Board")
    assert recovered == [Name("John W", "Doe", "Jr")]


def test_a_list_of_names_gives_every_person() -> None:
    names = authors.recover_names("JANE DOE, RICHARD ROE and ANN POE")
    assert [authors.name_key(n) for n in names] == ["janedoe", "richardroe", "annpoe"]


@pytest.mark.parametrize(
    "part",
    [
        "Jane. Springfield",  # one word is not a full name
        "Jane - Springfield",
        "Jane, Springfield",
        "Example Free Press11 Example Free Press",
        "Springfield Republic11 Springfield Republic",
        "Springfield American-Statesman11 Springfield American-Statesman",
        "The Editorial Board",
        "a guest columnist",
        "Excerpted from an editorial in the Example News",
        "Former US president Jane Doe was awarded a prize",
        "Compiled by Jane Doe, who can be reached by mail",
        "member of the Example editorial board.",
        "Rep Jane Doe Guest essay",  # the name cannot be told from the words after it
    ],
)
def test_text_that_does_not_start_with_a_full_name_gives_nobody(part: str) -> None:
    assert authors.recover_names(part) == []


def test_a_role_after_the_comma_is_not_a_given_name() -> None:
    assert authors.parse_name("Jane Q. Doe, Director") is None
    assert authors.recover_names("Jane Q. Doe, Director") == [Name("Jane Q.", "Doe", "")]


def test_read_part_says_how_the_names_were_read() -> None:
    assert authors.read_part("Doe, Jane") == ([Name("Jane", "Doe", "")], "as_written")
    assert authors.read_part("Jane Doe. Springfield") == ([Name("Jane", "Doe", "")], "recovered")
    assert authors.read_part("The Editorial Board") == ([], "")


def test_people_include_recovered_names() -> None:
    raw = "Jane Doe. Springfield; The Editorial Board; Roe, Richard"
    assert authors.people(raw) == [Name("Jane", "Doe", ""), Name("Richard", "Roe", "")]


# --- corrections from the manual review --------------------------------------------


def test_read_byline_gives_each_person_once_with_how_it_was_read() -> None:
    raw = "Doe, Jane; Richard Roe. Springfield; DOE, JANE; The Editorial Board"
    assert authors.read_byline(raw) == [
        (Name("Jane", "Doe", ""), "as_written"),
        (Name("Richard", "Roe", ""), "recovered"),
    ]


def test_a_corrected_part_is_read_from_its_correction() -> None:
    corrections = {"Jane Doe, Springfield": "Doe, Jane"}
    assert authors.read_byline("Jane Doe, Springfield; Roe, Richard", corrections) == [
        (Name("Jane", "Doe", ""), "manual_review"),
        (Name("Richard", "Roe", ""), "as_written"),
    ]


def test_a_correction_can_name_two_people_or_nobody() -> None:
    corrections = {"Jane Doe, Richard Roe": "Doe, Jane; Roe, Richard", "Doe Roe, Ann": ""}
    assert [n for n, _ in authors.read_byline("Jane Doe, Richard Roe", corrections)] == [
        Name("Jane", "Doe", ""),
        Name("Richard", "Roe", ""),
    ]
    assert authors.read_byline("Doe Roe, Ann", corrections) == []


def test_people_use_the_corrections() -> None:
    assert authors.people("Doe Roe, Ann", {"Doe Roe, Ann": ""}) == []
    assert authors.people("Doe Roe, Ann") == [Name("Ann", "Doe Roe", "")]


# --- initials that look like a title or a suffix -----------------------------------


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("Doe, M.R.", Name("M.R.", "Doe", "")),
        ("M.S. Doe", Name("M.S.", "Doe", "")),
        ("Doe, J.R.", Name("J.R.", "Doe", "")),
        ("J.R. Doe", Name("J.R.", "Doe", "")),
        ("Doe, JR", Name("JR", "Doe", "")),
    ],
)
def test_initials_are_not_taken_for_a_title_or_a_suffix(part: str, expected: Name) -> None:
    assert authors.parse_name(part) == expected


def test_a_suffix_after_a_full_name_is_still_a_suffix() -> None:
    assert authors.parse_name("John Doe, Jr.") == Name("John", "Doe", "Jr")
    assert authors.parse_name("Doe, John, JR") == Name("John", "Doe", "Jr")
    assert authors.split_authors("Doe, John; J.R.") == ["Doe, John", "J.R."]
