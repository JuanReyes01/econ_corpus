"""Tests for econ_corpus.raw.prose on made-up texts."""

import pyarrow as pa
import pytest

from econ_corpus.raw import prose

ENOUGH = prose.MIN_OWN_WORDS
SENTENCE = "The price of bread went up again this year."  # nine words
LETTER = " ".join([SENTENCE] * 4)
assert len(SENTENCE.split()) < ENOUGH <= len(LETTER.split())


def test_the_words_of_a_plain_text_are_all_its_author_s() -> None:
    assert prose.own_words(SENTENCE) == len(SENTENCE.split())
    assert prose.own_words(f"{SENTENCE}\n\n  {SENTENCE}  ") == 2 * len(SENTENCE.split())


def test_the_count_stops_once_a_text_has_enough_words() -> None:
    assert prose.own_words(LETTER) == ENOUGH
    assert prose.own_words(" ".join([LETTER] * 50)) == ENOUGH
    assert prose.own_words(LETTER, enough=12) == 12


@pytest.mark.parametrize(
    "line",
    [
        "Credit: Jane Doe for The Daily Sample",
        "CREDIT: Jane Doe",
        "Crédito: Jane Doe",
        "Caption: A man holds a loaf of bread outside a bakery. PHOTOGRAPH BY JANE DOE",
        "Caption text only.",
        "Caption only",
        "Photo: A bakery in Sampletown (Jane Doe / For The Times)",
        "Photographer: Jane Doe",
        "Graphic: The price of bread since 1990",
        "Graphic-Chart: The price of bread",
        "Illustration Cartoon",
        "ILLUSTRATION BY JANE DOE",
        "Drawing: (Jane Doe)",
        "Cartoon",
        "See PDF for the full page",
        "The story text of this article is not available because of rights restrictions.",
        "Follow The New York Times Opinion section on social networks.",
        "Sign up for the Sample newsletter",
        "Read more:",
        "Source URL: https://example.org/bread",
        "_____",
        "---",
        "*",
        "-- Jane Doe",
        "--Jane Doe",
        "(Jane Doe / For The Times)",
    ],
)
def test_a_line_added_around_the_text_is_not_counted(line: str) -> None:
    assert prose.own_words(line) == 0
    assert prose.own_words(f"{SENTENCE}\n{line}\n{SENTENCE}") == 2 * len(SENTENCE.split())


@pytest.mark.parametrize(
    "line",
    [
        "He owes the bakery credit: nine loaves so far.",  # the mark opens the line
        "A caption would not explain this price.",
        "Cartoon characters eat no bread.",
        "The illustrations in the book are fine.",
        "Readers sign up for bread, not for speeches.",
        "More than a year ago this newspaper wrote:",
        "More bread is what the town asked for.",
        "More importantly:",
        "More to the point:",
        "More troubling is what the mayor said last week:",
        "More important, the council never asked the town:",
        "More on that later, but first the facts.",
        "More from the council would help everyone in town.",
        "More by luck than design, the plan worked.",
        "My son is the cartoonist for the school paper, and he agrees.",
        "-- and the price of bread went up again",
    ],
)
def test_a_sentence_that_only_names_such_a_line_is_counted(line: str) -> None:
    assert prose.own_words(line) == len(line.split())


@pytest.mark.parametrize(
    "ending",
    [
        "More from Opinion:",
        "More from Jane Doe",
        "More by Jane Doe:",
        "Read more from Jane Doe's archive.",
        "See more cartoons",
        "See more Jane Doe cartoons and blog posts:",
        "More cartoons:",
        "Read more about the price of bread",
        "Read more form Jane Doe:",
        "More by Jane Doe: The price of bread went up again",
        "More on this",
        "AuthorAffiliation JANE DOE Jane Doe is an editorial cartoonist for The Daily Sample.",
        "Read more Jane Doe:",
        "More Jane Doe on the price of bread:",
        "Previous Jane Doe cartoons",
        "The Times is committed to publishing a diversity of letters to the editor.",
        "Jane Doe is an editorial cartoonist for The Daily Sample.",
        "Jane Doe is the cartoonist of The Daily Sample and the author of two books.",
        "Editorial cartoonist Jane Doe captures the news of the week.",
    ],
)
def test_from_a_list_of_links_or_a_note_on_the_author_nothing_is_counted(ending: str) -> None:
    assert prose.own_words(f"{ending}\n{LETTER}") == 0
    assert prose.own_words(f"{SENTENCE}\n{ending}\n{LETTER}") == len(SENTENCE.split())


def test_an_ending_after_enough_words_changes_nothing() -> None:
    assert prose.own_words(f"{LETTER}\nMore from Opinion:\nA title\nAnother title") == ENOUGH


def test_a_long_text_is_not_read() -> None:
    # In a long text the words of an ending open a paragraph, and furniture is a detail.
    long_text = " ".join(["bread"] * prose.LONG_TEXT_WORDS)
    assert prose.own_words(f"More on the price of bread:\n{long_text}") == ENOUGH
    assert prose.own_words(f"Caption: {long_text}") == ENOUGH
    almost_long = " ".join(["bread"] * (prose.LONG_TEXT_WORDS - 2))
    assert prose.own_words(f"Caption: {almost_long}") == 0


def test_the_address_of_the_page_at_the_end_of_a_line_is_not_counted() -> None:
    assert prose.own_words(f"{SENTENCE} Source URL: https://example.org/a b c") == len(
        SENTENCE.split()
    )


def test_a_missing_or_empty_text_has_no_words() -> None:
    assert [prose.own_words(text) for text in (None, "", " \n \n")] == [0, 0, 0]


def test_the_counts_of_a_column_of_texts_come_in_order() -> None:
    texts = pa.array([LETTER, None, SENTENCE, "Credit: Jane Doe"], type=pa.string())
    assert prose.own_word_counts(texts) == [ENOUGH, 0, len(SENTENCE.split()), 0]
