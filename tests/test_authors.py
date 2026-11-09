"""Tests for econ_corpus.names.authors, using made-up names only."""

import pytest

from econ_corpus.names import authors, bylines, name_lists, name_tokens, parts, spelling
from econ_corpus.names.authors import Name

# --- splitting a byline into parts -------------------------------------------------


def test_none_and_empty_bylines_have_no_parts() -> None:
    assert bylines.split_authors(None) == []
    assert bylines.split_authors("  ;  ") == []


def test_semicolon_separates_authors() -> None:
    assert bylines.split_authors("Doe, Jane; Roe, Richard A") == ["Doe, Jane", "Roe, Richard A"]


def test_a_suffix_standing_alone_joins_the_name_before_it() -> None:
    assert bylines.split_authors("Doe, John W; Jr.") == ["Doe, John W, Jr"]
    assert bylines.split_authors("Doe, John W; Jr.; Roe, Ann") == ["Doe, John W, Jr", "Roe, Ann"]


def test_a_suffix_with_no_name_before_it_is_kept_as_written() -> None:
    assert bylines.split_authors("Jr.") == ["Jr."]


@pytest.mark.parametrize("joiner", [" and ", " AND ", " And ", " & "])
def test_and_separates_names_written_without_commas(joiner: str) -> None:
    assert bylines.split_authors(f"Jane Doe{joiner}Richard Roe") == ["Jane Doe", "Richard Roe"]


def test_and_inside_a_comma_form_is_not_a_separator() -> None:
    assert bylines.split_authors("Doe, Jane and Co") == ["Doe, Jane and Co"]


@pytest.mark.parametrize("raw", ["By Jane Doe", "by Jane Doe", "BY Jane Doe"])
def test_leading_by_is_removed(raw: str) -> None:
    assert bylines.split_authors(raw) == ["Jane Doe"]


def test_a_name_that_starts_with_by_letters_is_not_cut() -> None:
    assert bylines.split_authors("Byron Doe") == ["Byron Doe"]


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
    assert spelling.display(Name("John W", "Doe", "Jr")) == "John W Doe Jr"


def test_display_fixes_names_written_in_capitals() -> None:
    assert spelling.display(Name("JANE Q", "O'DOE-ROE", "")) == "Jane Q O'Doe-Roe"
    assert spelling.display(Name("JANE", "del DOE", "")) == "Jane del Doe"
    assert spelling.display(Name("J.Q.", "DOE", "")) == "J.Q. Doe"


def test_display_leaves_mixed_case_names_alone() -> None:
    assert spelling.display(Name("Jane", "McDoe", "")) == "Jane McDoe"


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
    assert spelling.name_key(authors.parse_name(part)) == "janeqdoe"


def test_key_joins_initials_however_they_are_spaced() -> None:
    keys = {
        spelling.name_key(authors.parse_name(p))
        for p in ("Doe, EJ, Jr", "Doe, E J, Jr", "E.J. Doe Jr.")
    }
    assert keys == {"ejdoejr"}


def test_key_ignores_accents_and_curly_apostrophes() -> None:
    assert spelling.name_key(Name("José", "O\u2019Doe", "")) == spelling.name_key(
        Name("Jose", "O'Doe", "")
    )


def test_key_keeps_suffix_and_middle_name_apart() -> None:
    plain = spelling.name_key(Name("John", "Doe", ""))
    assert spelling.name_key(Name("John", "Doe", "Jr")) != plain
    assert spelling.name_key(Name("John W", "Doe", "")) != plain


# --- people in a byline ------------------------------------------------------------


def test_people_returns_persons_in_order_and_drops_the_rest() -> None:
    raw = "Doe, Jane; The Editorial Board; Roe, Richard A"
    assert bylines.people(raw) == [Name("Jane", "Doe", ""), Name("Richard A", "Roe", "")]


def test_people_lists_a_person_once_per_byline() -> None:
    assert bylines.people("Doe, Jane; DOE, JANE") == [Name("Jane", "Doe", "")]


@pytest.mark.parametrize("raw", [None, "", "Anonymous", "The Editorial Board; Anonymous"])
def test_bylines_without_a_person_give_no_people(raw: str | None) -> None:
    assert bylines.people(raw) == []


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
    assert bylines.is_signed(raw) is expected


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
    assert [spelling.name_key(n) for n in parts.recover_names(part)] == ["janedoe"]


def test_recovered_name_keeps_middle_initial_and_suffix() -> None:
    assert parts.recover_names("Jane Q. Doe, MD") == [Name("Jane Q.", "Doe", "")]
    recovered = parts.recover_names("John W Doe Jr, President, Example Board")
    assert recovered == [Name("John W", "Doe", "Jr")]


def test_a_list_of_names_gives_every_person() -> None:
    names = parts.recover_names("JANE DOE, RICHARD ROE and ANN POE")
    assert [spelling.name_key(n) for n in names] == ["janedoe", "richardroe", "annpoe"]


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
    assert parts.recover_names(part) == []


def test_a_role_after_the_comma_is_not_a_given_name() -> None:
    assert authors.parse_name("Jane Q. Doe, Director") is None
    assert parts.recover_names("Jane Q. Doe, Director") == [Name("Jane Q.", "Doe", "")]


def test_read_part_says_how_the_names_were_read() -> None:
    assert parts.read_part("Doe, Jane") == ([Name("Jane", "Doe", "")], "as_written")
    assert parts.read_part("Jane Doe. Springfield") == ([Name("Jane", "Doe", "")], "recovered")
    assert parts.read_part("The Editorial Board") == ([], "")


def test_people_include_recovered_names() -> None:
    raw = "Jane Doe. Springfield; The Editorial Board; Roe, Richard"
    assert bylines.people(raw) == [Name("Jane", "Doe", ""), Name("Richard", "Roe", "")]


# --- corrections from the manual review --------------------------------------------


def test_read_byline_gives_each_person_once_with_how_it_was_read() -> None:
    raw = "Doe, Jane; Richard Roe. Springfield; DOE, JANE; The Editorial Board"
    assert bylines.read_byline(raw) == [
        (Name("Jane", "Doe", ""), "as_written"),
        (Name("Richard", "Roe", ""), "recovered"),
    ]


def test_a_corrected_part_is_read_from_its_correction() -> None:
    corrections = {"Jane Doe, Springfield": "Doe, Jane"}
    assert bylines.read_byline("Jane Doe, Springfield; Roe, Richard", corrections) == [
        (Name("Jane", "Doe", ""), "manual_review"),
        (Name("Richard", "Roe", ""), "as_written"),
    ]


def test_a_correction_can_name_two_people_or_nobody() -> None:
    corrections = {"Jane Doe, Richard Roe": "Doe, Jane; Roe, Richard", "Doe Roe, Ann": ""}
    assert [n for n, _ in bylines.read_byline("Jane Doe, Richard Roe", corrections)] == [
        Name("Jane", "Doe", ""),
        Name("Richard", "Roe", ""),
    ]
    assert bylines.read_byline("Doe Roe, Ann", corrections) == []


def test_people_use_the_corrections() -> None:
    assert bylines.people("Doe Roe, Ann", {"Doe Roe, Ann": ""}) == []
    assert bylines.people("Doe Roe, Ann") == [Name("Ann", "Doe Roe", "")]


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
    assert bylines.split_authors("Doe, John; J.R.") == ["Doe, John", "J.R."]


# --- institutions, particles and capitals (found in code review) -------------------


@pytest.mark.parametrize(
    "part",
    [
        "The Times, London",  # an institution word in a family name of several words
        "Example Times, Springfield",
        "Southtown, Daily",
        "Advertiser, Springfield Daily",
        "Affairs, International",
        "Today, Springfield",
        "Democrat, Springfield",
        "Le Monde",  # an article is not a given name
        "El Example",
        "Der Example",
        "Springfield Daily",
        "International Affairs",
    ],
)
def test_institutions_are_not_persons(part: str) -> None:
    assert authors.parse_name(part) is None
    assert parts.recover_names(part) == []


def test_one_word_family_names_that_are_also_institution_words_stay() -> None:
    assert authors.parse_name("Post, Jane") == Name("Jane", "Post", "")
    assert authors.parse_name("Pollard-Post, Jane") == Name("Jane", "Pollard-Post", "")
    assert authors.parse_name("Record, Jane") == Name("Jane", "Record", "")


def test_capitalised_al_is_a_given_name_not_a_particle() -> None:
    assert authors.parse_name("Al Doe") == Name("Al", "Doe", "")
    assert authors.parse_name("Jane Al Doe") == Name("Jane Al", "Doe", "")
    assert spelling.display(Name("AL", "DOE", "")) == "Al Doe"


def test_lower_case_particles_still_belong_to_the_family_name() -> None:
    assert authors.parse_name("Jane al Doe") == Name("Jane", "al Doe", "")
    assert authors.parse_name("Jane Van Doe") == Name("Jane", "Van Doe", "")


def test_capitals_fix_handles_particles_and_possessives() -> None:
    assert spelling.display(Name("JANE", "DEL DOE", "")) == "Jane Del Doe"
    assert spelling.display(Name("JANE", "del DOE", "")) == "Jane del Doe"
    assert spelling.display(Name("JANE", "O'DOE", "")) == "Jane O'Doe"
    assert spelling.display(Name("JANE DOE'S", "COLUMN", "")) == "Jane Doe's Column"


# --- second code review ------------------------------------------------------------


def test_a_family_name_cut_off_by_a_semicolon_is_joined_to_its_given_name() -> None:
    assert bylines.split_authors("Doe; , Jane") == ["Doe, Jane"]
    assert bylines.split_authors("DOE; , JANE Q.; Roe, Richard") == [
        "DOE, JANE Q.",
        "Roe, Richard",
    ]
    assert bylines.people("Doe; , Jane") == [Name("Jane", "Doe", "")]


def test_a_comma_first_piece_is_left_alone_after_a_full_part() -> None:
    assert bylines.split_authors("Doe, Jane; , Richard") == ["Doe, Jane", ", Richard"]
    assert bylines.split_authors("Jane Doe; , Richard") == ["Jane Doe", ", Richard"]
    assert bylines.split_authors(", Jane") == [", Jane"]


def test_les_is_a_given_name_not_an_article() -> None:
    assert authors.parse_name("Les Doe") == Name("Les", "Doe", "")
    assert authors.parse_name("Las Example") is None


# --- names the rules refused but a reviewer wrote ----------------------------------


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("Red Star, Jane", Name("Jane", "Red Star", "")),  # an institution word in the name
        ("Doe, Jane 8.", Name("Jane 8.", "Doe", "")),  # a digit that belongs to the name
        ("Doe, JD", Name("JD", "Doe", "")),  # initials that look like a degree
        ("García De La Doe, María Antonia", Name("María Antonia", "García De La Doe", "")),
        ("Doe, John W, Jr", Name("John W", "Doe", "Jr")),
        (" Doe ,  Jane ", Name("Jane", "Doe", "")),
    ],
)
def test_a_reviewed_name_is_taken_as_the_reviewer_wrote_it(part: str, expected: Name) -> None:
    assert authors.reviewed_name(part) == expected


@pytest.mark.parametrize(
    "part", ["ask the editor", "Doe", "Doe, ", ", Jane", "Doe, Jane, Springfield"]
)
def test_a_reviewed_name_must_still_be_family_comma_given(part: str) -> None:
    assert authors.reviewed_name(part) is None


def test_corrections_are_read_as_reviewed_names() -> None:
    corrections = {
        "Jane Red Star": "Red Star, Jane",
        "Doe, Al Roe and Ann": "Doe, Ann; Roe, Al 2.",
    }
    assert bylines.read_byline("Jane Red Star; Doe, Al Roe and Ann", corrections) == [
        (Name("Jane", "Red Star", ""), "manual_review"),
        (Name("Ann", "Doe", ""), "manual_review"),
        (Name("Al 2.", "Roe", ""), "manual_review"),
    ]


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("al-Doe, Jane", Name("Jane", "al-Doe", "")),
        ("deDoe, Jane", Name("Jane", "deDoe", "")),
        ("d'Doe, Jane", Name("Jane", "d'Doe", "")),
        ("Jane al-Doe", Name("Jane", "al-Doe", "")),
    ],
)
def test_a_family_name_with_a_small_first_letter_and_a_capital_inside_is_read(
    part: str, expected: Name
) -> None:
    assert authors.parse_name(part) == expected


def test_a_family_name_with_no_capital_at_all_is_still_refused() -> None:
    assert authors.parse_name("ehle, Jane Von") is None
    assert authors.parse_name("Jane is here") is None


def test_a_recovered_name_goes_on_through_a_small_first_letter_with_a_capital_inside() -> None:
    recovered = parts.recover_names("Dr. Jane al-Doe is a member of the Example parliament.")
    assert recovered == [Name("Jane", "al-Doe", "")]


# --- found in the audit ------------------------------------------------------------


@pytest.mark.parametrize(
    "part",
    [
        "Jane Q. Doe, MD",
        "Jane Q. Doe MD",
        "Jane Q. Doe M.D.",
        "Doe, Jane Q., M.D.",
        "Doe, Jane Q., PhD",
    ],
)
def test_a_degree_after_the_name_is_dropped(part: str) -> None:
    assert spelling.name_key(authors.parse_name(part)) == "janeqdoe"


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("DOE, By JANE", Name("JANE", "DOE", "")),  # 'By' left inside the byline
        ("Sen, Jane Doe", Name("Jane", "Doe", "")),  # a title where the family name goes
        ("N.J., Jane Q. Doe", Name("Jane Q.", "Doe", "")),  # a state where the family name goes
        ("State Rep Jane Doe", Name("Jane", "Doe", "")),
        ("Vice President Jane Doe", Name("Jane", "Doe", "")),
        ("Retired Brigadier General Jane Doe", Name("Jane", "Doe", "")),
        ("Sister Jane Doe", Name("Jane", "Doe", "")),
    ],
)
def test_titles_and_debris_around_a_name_are_dropped(part: str, expected: Name) -> None:
    assert authors.parse_name(part) == expected


@pytest.mark.parametrize(
    "part", ["Doe, Jane Roe and Ann", "Doe, Jane & Ann", "Jane Z", "Mayor Doe"]
)
def test_these_parts_do_not_read_as_one_person(part: str) -> None:
    assert authors.parse_name(part) is None


def test_co_authors_scrambled_by_the_export_are_put_back() -> None:
    # 'Jane Roe and Ann Doe' is exported as 'Doe, Jane Roe and Ann'.
    assert parts.recover_names("Doe, Jane Roe and Ann") == [
        Name("Jane", "Roe", ""),
        Name("Ann", "Doe", ""),
    ]
    three = parts.recover_names("Doe, Jane Roe, Al Poe and Ann Q.")
    assert [spelling.name_key(n) for n in three] == ["janeroe", "alpoe", "annqdoe"]


def test_a_given_name_cut_off_and_holding_a_list_is_unscrambled_too() -> None:
    names = bylines.read_byline("Doe; , Jane Roe and Ann")
    assert [spelling.name_key(n) for n, _ in names] == ["janeroe", "anndoe"]


def test_a_stray_period_inside_a_name_does_not_cut_it() -> None:
    assert parts.recover_names("Jane Z . Doe") == [Name("Jane Z", "Doe", "")]


def test_capitals_fix_knows_mc_and_mac() -> None:
    assert spelling.display(Name("JANE", "McDOE", "")) == "Jane McDoe"
    assert spelling.display(Name("JANE Q", "MacDOE", "")) == "Jane Q MacDoe"
    assert spelling.display(Name("Jane", "McDoe", "")) == "Jane McDoe"
    assert spelling.display(Name("JANE", "MACE", "")) == "Jane Mace"


# --- findings of the second independent audit ---------------------------------------

JANE = Name("Jane", "Doe", "")


def test_a_degree_does_not_remove_the_only_given_name() -> None:
    assert authors.parse_name("Doe, JD") == Name("JD", "Doe", "")
    assert authors.parse_name("Jane Doe, JD") == JANE


@pytest.mark.parametrize(
    ("part", "suffix"), [("Doe, John Jr.", "Jr"), ("Doe, John Jr", "Jr"), ("Doe, John III", "III")]
)
def test_a_suffix_after_the_given_name_is_a_suffix(part: str, suffix: str) -> None:
    assert authors.parse_name(part) == Name("John", "Doe", suffix)


def test_initials_alone_are_never_a_family_name() -> None:
    assert authors.parse_name("E., Adlai") is None
    assert parts.read_part("R., Jane Q. Doe and Ann") == ([], "")


@pytest.mark.parametrize("part", ["Jane St. Doe", "St. Doe, Jane", "Jane St Doe"])
def test_a_saint_in_the_family_name_is_read(part: str) -> None:
    assert spelling.name_key(authors.parse_name(part)) == "janestdoe"
    assert authors.parse_name(part).family.split()[-1] == "Doe"


def test_a_saint_does_not_end_a_recovered_name() -> None:
    assert parts.recover_names("Jane St. Doe, Springfield") == [Name("Jane", "St. Doe", "")]


@pytest.mark.parametrize("raw", ["ByJane Doe", "Doe, ByJane"])
def test_by_glued_to_the_name_is_removed(raw: str) -> None:
    assert bylines.people(raw) == [JANE]


@pytest.mark.parametrize(
    "part", ["Jane DoeGuest essay", "essay, Jane DoeGuest", "DoeGuest essay, Jane"]
)
def test_a_label_glued_to_the_name_is_removed(part: str) -> None:
    assert parts.read_part(part) == ([JANE], "as_written")


@pytest.mark.parametrize(
    "part",
    [
        "Jane Doe is on vacation.",
        "Jane Doe is off today.",
        "Jane Doe is on book leave until May.",
        "Jane Doe is on a book tour.",
        "Jane Doe is on",
        "Jane Doe and Ann Roe are on vacation.",
        "Jane Doe contributed reporting.",
    ],
)
def test_a_note_about_someone_who_did_not_write_names_nobody(part: str) -> None:
    assert bylines.people(part) == []


@pytest.mark.parametrize(
    "part",
    [
        "Jane Doe is on the board of the Example Fund.",
        "Jane Doe's column appears regularly in the",
        "Jane Doe of Springfield",
        "Jane Doe is a teacher",
        "Jane Doe writes about Springfield schools",
    ],
)
def test_a_sentence_about_the_author_still_names_her(part: str) -> None:
    assert parts.read_part(part) == ([JANE], "recovered")


@pytest.mark.parametrize(
    "part", ["Jane Do e Roe", "Jane Roe ll Doe", "Jane Doe covers Springfield"]
)
def test_a_name_that_a_small_word_may_have_broken_is_not_read(part: str) -> None:
    assert parts.read_part(part) == ([], "")


def test_and_does_not_split_a_sentence_about_one_author() -> None:
    raw = "Jane Doe is a fellow at the Example Institute and Richard Roe was her teacher"
    assert bylines.people(raw) == [JANE]


def test_and_still_splits_names_when_text_follows_the_last() -> None:
    raw = "Jane Doe and Richard Roe of Springfield"
    assert bylines.people(raw) == [JANE, Name("Richard", "Roe", "")]


def test_scrambled_co_authors_need_and_before_the_last_given_name() -> None:
    assert name_lists.unscrambled("Doe, Jane Roe and Ann") == [
        Name("Jane", "Roe", ""),
        Name("Ann", "Doe", ""),
    ]
    assert name_lists.unscrambled("Doe, Jane Roe, Ann") == []


def test_scrambled_co_authors_need_a_family_name_alone_before_the_comma() -> None:
    assert name_lists.unscrambled("Jane Doe, Richard Roe and Springfield") == []
    assert name_lists.unscrambled("van Doe, Jane Roe and Ann")[1] == Name("Ann", "van Doe", "")


@pytest.mark.parametrize(
    "part",
    [
        "Example Development Agency",
        "Example Agriculture Organization in Springfield",
        "Springfield Community Clinic",
        "Example Rights Project",
        "Springfield School Administration",
        "Example Government Commission",
    ],
)
def test_more_institutions_are_not_persons(part: str) -> None:
    assert bylines.people(part) == []


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        (Name("JANE", "Doe", ""), "Jane Doe"),  # one word left in capitals
        (Name("JANE", "DeDOE", ""), "Jane DeDoe"),
        (Name("Jane", "LaDOE", ""), "Jane LaDoe"),
        (Name("JD", "Doe", ""), "JD Doe"),  # two capitals are initials
        (Name("Jane", "de Doe", ""), "Jane de Doe"),
    ],
)
def test_display_fixes_single_words_with_odd_capitals(name: Name, shown: str) -> None:
    assert spelling.display(name) == shown


def test_a_title_where_the_family_name_goes_is_told_apart() -> None:
    assert name_tokens.is_title("Sen")
    assert name_tokens.is_title("N.J.")
    assert not name_tokens.is_title("Doe")


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        (Name("JQD", "Doe", ""), "JQD Doe"),  # capitals with no vowel are initials
        (Name("JANE", "d'DOE", ""), "Jane d'Doe"),
        (Name("JANE", "al-DOE", ""), "Jane al-Doe"),
    ],
)
def test_display_tells_initials_from_names_in_capitals(name: Name, shown: str) -> None:
    assert spelling.display(name) == shown


def test_text_after_the_end_of_a_sentence_does_not_stop_a_recovered_name() -> None:
    assert parts.recover_names("Jane Doe. // Richard Roe") == [JANE]
    assert parts.recover_names("Jane Doe's novel Springfield") == [JANE]


def test_and_glued_to_a_name_that_starts_with_and_is_put_back() -> None:
    assert bylines.split_authors("Jane Doe andrew Roe") == ["Jane Doe", "Andrew Roe"]
    assert bylines.split_authors("Jane Doe andy Roe") == ["Jane Doe", "Andy Roe"]
    assert bylines.split_authors("Andrew Roe") == ["Andrew Roe"]


def test_a_suffix_in_a_list_of_names_does_not_make_it_one_name() -> None:
    assert bylines.people("Jane Doe, Richard Roe Jr.") == [JANE, Name("Richard", "Roe", "Jr")]


def test_a_town_before_a_name_in_capitals_is_not_a_family_name() -> None:
    assert authors.parse_name("Springfield, JANE DOE") is None
    assert authors.parse_name("DOE, JANE Q") == Name("JANE Q", "DOE", "")
    assert authors.parse_name("Doe, J Q") == Name("J Q", "Doe", "")
    assert authors.parse_name("Doe, J. Q.") == Name("J. Q.", "Doe", "")
    assert authors.parse_name("Doe, JANE Q.") == Name("JANE Q.", "Doe", "")


def test_a_small_st_is_not_a_saint() -> None:
    assert not name_tokens.is_particle("st")
    assert name_tokens.is_particle("St.")


@pytest.mark.parametrize("part", ["Jane Doe Guest essay", "Jane Doe Gue st essay"])
def test_a_label_after_the_name_is_removed(part: str) -> None:
    assert parts.read_part(part) == ([JANE], "as_written")


def test_a_degree_not_in_capitals_is_never_a_given_name() -> None:
    assert authors.parse_name("Doe, Rn") is None
    assert authors.parse_name("Doe, PhD") is None


@pytest.mark.parametrize(
    "part", ["Committee., Jane Doe", "Class.'', Jane Doe", '1981.", Jane Doe']
)
def test_a_name_after_the_end_of_a_sentence_about_it_is_recovered(part: str) -> None:
    assert parts.read_part(part) == ([JANE], "recovered")


def test_two_names_after_the_end_of_a_sentence_are_both_recovered() -> None:
    assert parts.recover_names("Committee., Jane Doe and Richard Roe") == [
        JANE,
        Name("Richard", "Roe", ""),
    ]


@pytest.mark.parametrize("part", ["vacation., Jane Doe", "traveling., JANE DOE", "ill., Jane Doe"])
def test_a_moved_absence_word_stands_before_the_author_not_the_absent(part: str) -> None:
    # 'Jane Doe; Ann Roe is on vacation.' is exported as 'vacation., Jane Doe; Ann Roe is on'.
    assert spelling.name_key(parts.read_part(part)[0][0]) == "janedoe"


def test_the_cut_note_after_a_moved_absence_word_names_nobody() -> None:
    assert bylines.people("vacation., Jane Doe; Ann Roe is on") == [JANE]
    assert bylines.people("ill., Jane Doe; Ann Roe is") == [JANE]
    assert bylines.people("traveling., Jane Doe; Roe is, A M") == [JANE]


def test_a_suffix_before_the_comma_is_a_suffix() -> None:
    assert authors.parse_name("Doe Jr., John") == Name("John", "Doe", "Jr")
    assert authors.parse_name("III, John Q Doe") == Name("John Q", "Doe", "III")


@pytest.mark.parametrize(
    "part",
    ["Example Institution11 Example Institution", "Example Corporation", "Springfield Police"],
)
def test_institutions_named_twice_are_not_persons(part: str) -> None:
    assert bylines.people(part) == []


@pytest.mark.parametrize(
    "part",
    [
        "University, Example",
        "Association, Springfield",
        "Example LLP.",
        "Springfield's Untold Story",
        "Doe's, Jane",
        "St, Jane",
    ],
)
def test_these_parts_are_not_a_person(part: str) -> None:
    assert bylines.people(part) == []


def test_capitals_after_a_capitalised_prefix_are_fixed() -> None:
    assert spelling.display(Name("JANE", "El-DOE", "")) == "Jane El-Doe"


@pytest.mark.parametrize("part", ["Jane Q.Doe", "JANE Q.DOE", "Doe, J.Q.Jane"])
def test_an_initial_glued_to_the_next_word_is_set_apart(part: str) -> None:
    names, how = parts.read_part(part)
    assert how == "as_written"
    assert spelling.name_key(names[0]) in {"janeqdoe", "jqjanedoe"}
    assert all(
        word.endswith(".") or "." not in word for word in spelling.display(names[0]).split()
    )


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("Jane Doe.These are her own views.", JANE),
        ("JANE DOE.Jane Doe is a teacher in Springfield.", Name("JANE", "DOE", "")),
        ("Jane St.Doe", Name("Jane", "St. Doe", "")),
        ("Jane Q.O'Doe", Name("Jane Q.", "O'Doe", "")),
    ],
)
def test_a_period_glued_to_the_next_word_is_set_apart(part: str, expected: Name) -> None:
    assert parts.read_part(part)[0] == [expected]


def test_a_degree_written_without_its_last_period_is_still_a_degree() -> None:
    assert parts.read_part("Jane Q. Doe, M.D") == ([Name("Jane Q.", "Doe", "")], "as_written")


def test_an_author_who_contributed_her_own_piece_is_still_the_author() -> None:
    assert bylines.people("Jane Doe contributed this essay to the Springfield Review") == [JANE]


@pytest.mark.parametrize(
    "part",
    [
        "Jane Doe, Ann Roe and Richard Poe contributed reporting for this article.",
        "Jane Doe is on v acation.",
        "Former Global Example Coordinator",
        "Retired US Army captain",
        "Taking Exception",
        "Character Sketch",
        "CEO, Example",
        "Ventures, Example",
        "Republicans, Example Cabin",
        "Supreme Court",
    ],
)
def test_notes_roles_and_rubrics_are_not_persons(part: str) -> None:
    assert bylines.people(part) == []


def test_and_inside_a_note_after_the_name_in_capitals_does_not_split() -> None:
    raw = "JANE DOE. Jane Doe is professor of Law and Criminal Justice at Example University."
    assert bylines.people(raw) == [Name("JANE", "DOE", "")]


def test_pieces_of_a_note_after_a_sentence_about_the_author_are_not_authors() -> None:
    raw = "Jane Q.Doe; Doe was a speechwriter for Presidents Poe; Roe, Richard; Poe, Senator Ann"
    assert bylines.people(raw) == [Name("Jane Q.", "Doe", "")]


def test_a_second_author_with_her_own_sentence_is_still_read() -> None:
    raw = "Jane Doe is a teacher in Springfield; Richard Roe is a nurse in Shelbyville"
    assert bylines.people(raw) == [JANE, Name("Richard", "Roe", "")]


@pytest.mark.parametrize(("part", "suffix"), [("Jane Doe 3d", "III"), ("Doe, Jane 2d", "II")])
def test_ordinal_suffixes_are_read(part: str, suffix: str) -> None:
    assert authors.parse_name(part).suffix == suffix


def test_reader_glued_to_the_name_is_removed() -> None:
    assert parts.read_part("Jane Q DoeReader") == ([Name("Jane Q", "Doe", "")], "as_written")


def test_display_fixes_a_mc_name_in_capitals_and_keeps_numerals() -> None:
    assert spelling.display(Name("Jane", "MCDOE", "")) == "Jane McDoe"
    assert spelling.display(Name("JANE", "MCDOE", "")) == "Jane McDoe"
    assert spelling.display(Name("Jane", "Doe III", "")) == "Jane Doe III"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Doe, Temple", [Name("Temple", "Doe", "")]),
        ("Jane Court and Richard Roe", [Name("Jane", "Court", ""), Name("Richard", "Roe", "")]),
        ("Rear Adm. Jane Doe", [JANE]),
        ("Sens. Jane Doe", [JANE]),
    ],
)
def test_names_that_hold_a_word_of_an_institution_or_a_rank(raw: str, expected: list) -> None:
    assert bylines.people(raw) == expected


def test_a_sentence_that_ends_does_not_hide_the_authors_after_it() -> None:
    raw = "Jane Doe. Springfield. Editor's Note: The writer is a teacher.; Roe Shelbyville, Ann"
    assert [spelling.name_key(n) for n in bylines.people(raw)] == ["janedoe", "annroeshelbyville"]


def test_an_editors_note_cut_short_does_not_hide_the_next_letter_writers() -> None:
    raw = "Jane Doe. Springfield. Editor's Note: The writer is director of the Example; Roe, Ann"
    assert [spelling.name_key(n) for n in bylines.people(raw)] == ["janedoe", "annroe"]


def test_regressions_found_while_comparing_readings() -> None:
    assert spelling.name_key(authors.parse_name("Do us, Jane")) == "janedous"  # a stray space
    assert bylines.people("Jane Doe Jr., Richard Roe") == [
        Name("Jane", "Doe", "Jr"),
        Name("Richard", "Roe", ""),
    ]
    assert bylines.people("US Rep Jane Doe") == [JANE]
    raw = "This article was written jointly by Jane Doe, Example president; "
    raw += "Richard Roe, Example Borough president"
    assert Name("Richard", "Roe", "") in bylines.people(raw)


# --- findings of the fourth independent audit -----------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # A town where the family name goes; the note gives the name without it.
        ("Springfield, Jane Doe; Jane Doe, an author, lives in", [JANE]),
        # Given and family name the wrong way round; the note has them in order.
        ("Jane, Doe; Jane Doe lives in Springfield.", [JANE]),
        # The note gives the same name with its suffix.
        ("Roe, Jane McC; Jane McC. Roe Jr. is a senator.", [Name("Jane McC.", "Roe", "Jr")]),
        # A slip of one letter in the note.
        ("DOE, JANE H; Jane H. Dow lives in Springfield.", [Name("JANE H", "DOE", "")]),
        # The note adds a middle initial.
        ("Doe, Jane; Jane Q. Doe is a teacher.", [JANE]),
    ],
)
def test_a_note_that_repeats_the_author_adds_no_second_author(raw: str, expected: list) -> None:
    assert bylines.people(raw) == expected


def test_a_note_about_another_person_still_adds_her() -> None:
    assert bylines.people("Doe, Jane; Richard Roe is a teacher.") == [
        JANE,
        Name("Richard", "Roe", ""),
    ]


@pytest.mark.parametrize(
    "part", ["Jane Do rgan", "Jane Doe teaches", "Former Example Security chief"]
)
def test_one_small_word_after_a_name_is_left_for_review(part: str) -> None:
    assert parts.read_part(part) == ([], "")


def test_an_ordinal_suffix_stays_with_a_recovered_name() -> None:
    raw = "Jane Doe 3d; Jane Doe 3d lives in Springfield."
    assert bylines.people(raw) == [Name("Jane", "Doe", "III")]


def test_a_cut_note_counts_only_after_a_moved_word() -> None:
    assert bylines.people("By Jane Doe III. Jane Doe III is") == [Name("Jane", "Doe", "III")]
    assert bylines.people("traveling., Jane Doe; Roe is, A M") == [JANE]
    assert bylines.people("ill., Jane Doe; Ann Roe is") == [JANE]


def test_a_sentence_that_ended_inside_a_part_hides_nobody() -> None:
    raw = "Doe, Jane; Jane Doe is a former editorial writer. ANN POE; Roe, Richard"
    assert Name("Richard", "Roe", "") in bylines.people(raw)


@pytest.mark.parametrize("part", ["Cardinal Jane Doe", "Det. Jane Doe", "Archbishop Jane Doe"])
def test_more_titles_before_a_name_are_dropped(part: str) -> None:
    assert bylines.people(part) == [JANE]


def test_a_bank_after_a_name_is_not_a_given_name() -> None:
    assert bylines.people("Jane Doe, World Bank") == [JANE]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Doe, Jane Q; Jane Doe is a professor.", [Name("Jane Q", "Doe", "")]),
        ("Doe, Jane, Jr.; Jane Doe is a professor.", [Name("Jane", "Doe", "Jr")]),
        ("Roe, Mary Ann; Ann Roe is her daughter.", [Name("Mary Ann", "Roe", "")]),
    ],
)
def test_a_shorter_name_in_the_note_does_not_replace_the_fuller_one(
    raw: str, expected: list
) -> None:
    assert bylines.people(raw) == expected


def test_father_and_son_in_one_byline_are_two_people() -> None:
    assert bylines.people("Doe, John, Sr.; John Doe Jr. is a student.") == [
        Name("John", "Doe", "Sr"),
        Name("John", "Doe", "Jr"),
    ]


def test_names_listed_together_are_not_compared_with_each_other() -> None:
    assert [n.given for n in bylines.people("Mark Doe, Mary Doe and Ann Roe")] == [
        "Mark",
        "Mary",
        "Ann",
    ]


def test_a_note_that_spells_the_author_the_same_way_changes_nothing() -> None:
    assert bylines.read_byline("Doe, Jane Q; Jane Q. Doe lives in Springfield.") == [
        (Name("Jane Q", "Doe", ""), "as_written")
    ]


def test_regressions_found_while_comparing_readings_again() -> None:
    # A family name that is also a title ends the name like any other word.
    assert bylines.people("JANE BISHOP. Jane Bishop (D-Springfield) represents the district") == [
        Name("JANE", "BISHOP", "")
    ]
    # Initials inside an unfinished sentence do not end it.
    raw = "Jane Q.Doe; Doe was a speechwriter for Presidents John F. Poe; Roe, Richard"
    assert bylines.people(raw) == [Name("Jane Q.", "Doe", "")]
    glued = parts.read_part("Jane Q DoeReader essay")
    assert glued == ([Name("Jane Q", "Doe", "")], "as_written")


def test_a_family_name_cut_before_is_starts_no_sentence() -> None:
    assert Name("Richard", "Roe", "") in bylines.people("Do is, Jane G; Roe, Richard")


def test_a_note_cut_after_lives_still_names_its_author() -> None:
    assert parts.read_part("Jane Doe lives") == ([JANE], "recovered")


@pytest.mark.parametrize(
    "raw",
    [
        "Springfield., JANE DOEWOOD; Jnae Doewood lives in",  # two letters in the given name
        "Doewood, Jane; Jane Doewoodis host of a programme.",  # 'is' glued to the family name
        "Doewood, Jane; Jane Doewo od is a teacher.",  # the family name cut by a stray space
        "Doewood, Jan; Janet Doewood is a teacher.",  # a short form of the given name
    ],
)
def test_a_note_that_misspells_the_author_adds_no_second_author(raw: str) -> None:
    assert len(bylines.people(raw)) == 1


def test_and_or_by_before_a_name_in_any_part_is_dropped() -> None:
    assert bylines.people("Doe, Jane; And Richard Roe") == [JANE, Name("Richard", "Roe", "")]
    assert bylines.people("By Richard Roe, Jr.") == [Name("Richard", "Roe", "Jr")]


def test_two_people_with_one_family_name_and_initial_are_two_people() -> None:
    raw = "JANE DOE AND JOHN DOE. Jane and John Doe live in Springfield."
    assert [n.given for n in bylines.people(raw)] == ["JANE", "JOHN"]


def test_a_family_name_written_again_after_the_given_names_is_read_once() -> None:
    assert authors.parse_name("Doe, Jane Q. Doe") == Name("Jane Q.", "Doe", "")


def test_a_role_after_a_name_is_not_a_given_name() -> None:
    assert bylines.people("By Jane Q Doe, Publisher") == [Name("Jane Q", "Doe", "")]


def test_a_part_that_starts_with_a_comma_names_nobody() -> None:
    assert authors.parse_name(", Jane Doe") is None


def test_an_abbreviated_mc_name_does_not_end_the_name() -> None:
    expected = [Name("Jane McC.", "Roe", "Jr")]
    assert parts.read_part("Jane McC. Roe Jr. is a senator from Springfield.")[0] == expected
    assert authors.parse_name("Roe, Jane McC., Jr") == Name("Jane McC.", "Roe", "Jr")


# --- findings of the sixth independent audit ------------------------------------------


@pytest.mark.parametrize(
    "part",
    [
        "Jane Doe and Richard Roe, Example Staff",
        "Jane Doe and Richard Roe, Springfield Example Staff writers",
        "Jane Doe. Richard Roe. Written by members of the editorial board.",
        "Written by members of the editorial board.. Jane Doe. Richard Roe",
        "Jane Doe. Richard Roe. These are personal views of members of the editorial board.",
    ],
)
def test_a_list_of_names_before_or_after_a_note_gives_every_name(part: str) -> None:
    assert parts.read_part(part) == ([JANE, Name("Richard", "Roe", "")], "recovered")


def test_a_town_after_one_name_is_not_a_second_person() -> None:
    assert bylines.people("Jane Doe. Valley Stream. Editor's Note: The writer is a teacher.") == [
        JANE
    ]
    assert parts.recover_names("Jane Doe, Springfield Heights, Ill.") == [JANE]


def test_a_suffix_that_only_the_note_gives_is_kept() -> None:
    assert bylines.people("Doe, John E; John E. Doe Jr. lives in Springfield.") == [
        Name("John E.", "Doe", "Jr")
    ]


def test_a_suffix_glued_to_the_family_name_is_set_apart() -> None:
    assert parts.read_part("Jane DoeJr") == ([Name("Jane", "Doe", "Jr")], "as_written")


def test_a_family_name_with_a_small_first_letter_hides_nobody_after_it() -> None:
    raw = "deDoe, Jane; Roe, Richard; al-Poe, Ann; Moe, John"
    assert [n.family for n in bylines.people(raw)] == ["deDoe", "Roe", "al-Poe", "Moe"]


def test_a_suffix_written_twice_is_read_once() -> None:
    assert parts.read_part("Jane DoeJr. Jr. is chairman of the Example.")[0] == [
        Name("Jane", "Doe", "Jr")
    ]
    assert bylines.people("DoeJr, Jane; Jr.; a guest columnist") == [Name("Jane", "Doe", "Jr")]


def test_a_list_before_and_an_institution_keeps_its_names() -> None:
    assert parts.read_part("JANE DOE, RICHARD ROE AND EXAMPLE ASSOCIATES")[0] == [
        Name("JANE", "DOE", ""),
        Name("RICHARD", "ROE", ""),
    ]


def test_a_list_written_twice_before_its_note_is_read_once() -> None:
    raw = "Jane Doe and Richard Roe Jane Doe and Richard Roe are partners in the Example firm."
    assert bylines.people(raw) == [JANE, Name("Richard", "Roe", "")]


@pytest.mark.parametrize(
    "raw",
    [
        "Doewoodsen, Jane; Jane Doewodosen lives in Springfield.",
        "DOEWOOD, JANE; Jane Dowood is a teacher.",
    ],
)
def test_a_family_name_misspelt_by_more_than_a_letter_is_still_the_author(raw: str) -> None:
    assert len(bylines.people(raw)) == 1


@pytest.mark.parametrize(
    "part",
    ["Example Associates", "Example Resources Program", "Springfield Promise", "Example Science"],
)
def test_more_institution_tails_are_not_persons(part: str) -> None:
    assert bylines.people(part) == []


def test_a_role_in_a_list_after_one_name_is_not_a_person() -> None:
    assert bylines.people("Jane Q. Doe, Managing Partner, Example & Co.") == [
        Name("Jane Q.", "Doe", "")
    ]
    raw = "Jane Doe, Springfield District Attorney and a Democrat, was a member of the Example"
    assert bylines.people(raw) == [JANE]


# --- findings of the review of the sixth audit's fixes -------------------------------

BOARD_NOTE = "These are personal views of members of the editorial board."


@pytest.mark.parametrize(
    "part",
    [
        f"Jane Doe, Richard Roe, Ann Poe. {BOARD_NOTE}",
        "Jane Doe, Richard Roe and Ann Poe. Written by members of the editorial board.",
        "Written by members of the editorial board.. Jane Doe, Richard Roe & Ann Poe",
        "Jane Doe, Richard Roe, and Ann Poe",
        "Jane Doe, Richard Roe, and Ann Poe, Example Staff",
        "Jane Doe, Richard Roe, & Ann Poe",
    ],
)
def test_a_list_with_commas_gives_every_name(part: str) -> None:
    expected = [JANE, Name("Richard", "Roe", ""), Name("Ann", "Poe", "")]
    assert parts.read_part(part) == (expected, "recovered")


def test_scrambled_co_authors_with_a_comma_before_and_are_put_back() -> None:
    assert parts.read_part("Doe, Richard Roe, and Jane")[0] == [Name("Richard", "Roe", ""), JANE]


@pytest.mark.parametrize("again", ["Richard Roe", "Richard Row"])
def test_a_list_written_twice_in_a_part_with_a_comma_is_read_once(again: str) -> None:
    raw = f"Jane Doe and Richard Roe Jane Doe and {again} are partners in Example, Springfield."
    assert bylines.people(raw) == [JANE, Name("Richard", "Roe", "")]


def test_a_name_that_ends_like_the_first_of_its_list_is_not_cut() -> None:
    assert parts.read_part("Ann Lee and Mary Jo Ann Lee, Staff Writers")[0] == [
        Name("Ann", "Lee", ""),
        Name("Mary Jo Ann", "Lee", ""),
    ]


def test_a_family_name_two_letters_apart_in_the_note_is_still_the_author() -> None:
    assert len(bylines.people("Doeway, Jane; Jane Doeneway lives in Springfield.")) == 1


@pytest.mark.parametrize(
    "word",
    [
        "Resolution",
        "Forum",
        "Trust",
        "Equality",
        "Week",
        "Partner",
        "Managing",
        "Attorney",
        "District",
    ],
)
def test_each_new_institution_word_names_nobody(word: str) -> None:
    assert bylines.people(f"Springfield {word}") == []


def test_board_members_with_a_saint_name_or_in_capitals_are_read() -> None:
    note = "Written by members of the editorial board."
    assert parts.read_part(f"Jane St. John. Richard Roe. {note}")[0] == [
        Name("Jane", "St. John", ""),
        Name("Richard", "Roe", ""),
    ]
    assert parts.read_part(f"JANE DOE. RICHARD ROE. {note}")[0] == [
        Name("JANE", "DOE", ""),
        Name("RICHARD", "ROE", ""),
    ]


@pytest.mark.parametrize(
    "part",
    [
        "Jane Doe, Oak Park. Written by members of the editorial board.",
        "Written by members of the editorial board.. Jane Doe, Oak Park",
        "Jane Doe, Oak Park, Ill. Written by members of the editorial board.",
    ],
)
def test_a_town_after_a_board_member_is_not_a_second_member(part: str) -> None:
    assert parts.read_part(part)[0] == [JANE]


def test_board_members_after_an_ordinal_or_a_saint_in_capitals_are_read() -> None:
    note = "Written by members of the editorial board."
    assert parts.read_part(f"Jane Doe 3d. Richard Roe. {note}")[0] == [
        Name("Jane", "Doe", "III"),
        Name("Richard", "Roe", ""),
    ]
    assert parts.read_part(f"Jane ST. JOHN. Richard Roe. {note}")[0] == [
        Name("Jane", "ST. JOHN", ""),
        Name("Richard", "Roe", ""),
    ]


@pytest.mark.parametrize(
    ("second", "again"),
    [
        ("Dr. Richard Roe", "Dr. Richard Roe"),
        ("Richard Roe", "R. Roe"),
        ("Richard Roe", "Rick Roe"),
    ],
)
def test_a_list_written_twice_with_another_form_of_a_name_is_read_once(
    second: str, again: str
) -> None:
    raw = f"Jane Doe and {second} Jane Doe and {again} are partners in Example, Springfield."
    assert bylines.people(raw) == [JANE, Name("Richard", "Roe", "")]


def test_a_suffix_inside_a_list_of_board_members_ends_no_sentence() -> None:
    part = f"Jane Doe, Richard Roe Jr., Ann Poe. {BOARD_NOTE}"
    assert [n.family for n in parts.read_part(part)[0]] == ["Doe", "Roe", "Poe"]
    apart = f"Jane Doe Jr. Richard Roe. {BOARD_NOTE}"
    assert [n.family for n in parts.read_part(apart)[0]] == ["Doe", "Roe"]


# --- production credits ------------------------------------------------------------

CREDITS = {"Roe, Richard": bylines.CREDIT, "Poe, Ann": bylines.CREDIT}


def names_of(raw: str) -> list[str]:
    return [spelling.display(name) for name in bylines.people(raw, CREDITS)]


def test_a_credit_after_the_first_name_of_a_byline_is_not_an_author() -> None:
    assert names_of("Doe, Jane; Roe, Richard; Poe, Ann") == ["Jane Doe"]
    assert names_of("Doe, Jane; Roe, Richard; Coe, Tom") == ["Jane Doe", "Tom Coe"]


def test_a_credit_that_comes_first_or_alone_is_the_author() -> None:
    assert names_of("Roe, Richard") == ["Richard Roe"]
    assert names_of("Roe, Richard; Doe, Jane") == ["Richard Roe", "Jane Doe"]
    # Only the first of the credits: the others still come after a name.
    assert names_of("Roe, Richard; Poe, Ann") == ["Richard Roe"]


def test_a_credit_after_a_part_that_names_nobody_is_the_first_name() -> None:
    assert names_of("The Editorial Board; Roe, Richard; Doe, Jane") == ["Richard Roe", "Jane Doe"]


def test_a_credit_is_read_by_the_rules_and_says_how() -> None:
    assert bylines.read_byline("Roe, Richard", CREDITS) == [
        (Name("Richard", "Roe", ""), "as_written")
    ]
    assert bylines.read_byline("Roe, Richard", {}) == bylines.read_byline("Roe, Richard", CREDITS)


# --- compilers ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "byline",
    [
        "Compiled by Jane Doe",
        "COMPILED BY JANE DOE",
        "Compiled Jane Doe",
        "Compiled by Jane Doe. jane@example.com",
        "Compiled by Jane Doe, who can be reached at jane@example.com",
        "This page is compiled by Jane Doe, assistant editor",
        "In Other Words was compiled by Jane Doe",
        "Jane Doe compiled this report",
        "Compiled for The Times by Jane Doe",
        "Compiled by Jane Doe and Richard Roe",
        "Compiled by Jane Doe, with contributions from Richard Roe",
        "COMPILED FROM NEWS DISPATCHES",
    ],
)
def test_whoever_compiled_a_piece_is_not_its_author(byline: str) -> None:
    assert bylines.people(byline) == []
    assert parts.is_note(byline)


def test_the_author_next_to_a_compiler_is_still_read() -> None:
    assert names_of("Doe, Jane; Compiled by Richard Roe") == ["Jane Doe"]
    assert names_of("Compiled by Richard Roe; Doe, Jane") == ["Jane Doe"]


def test_a_name_that_only_looks_like_the_word_is_a_name() -> None:
    assert names_of("Compilet, Jane") == ["Jane Compilet"]


@pytest.mark.parametrize(
    "byline",
    [
        "Jane Doe and compiled by Richard Roe",
        "By Jane Doe. Compiled by Richard Roe",
        "Jane Doe, with data compiled by Richard Roe",
        "Jane Doe is a professor who compiled the index",
        "Jane Doe. She compiled the survey",
        "Jane Doe was an aide to Presidents Poe and compiled; Roe, Richard",
    ],
)
def test_the_word_compiled_after_an_author_does_not_remove_the_author(byline: str) -> None:
    assert [spelling.display(name) for name in bylines.people(byline)] == ["Jane Doe"]
    assert not parts.is_note(byline)
