"""Tests for econ_corpus.raw.language on made-up sentences."""

import pyarrow as pa
import pytest

from econ_corpus.raw import language

ENGLISH = (
    "The price of bread went up again this year, and it is not the first time that the people "
    "of this town have had to pay more for less. What would you do about it?"
)
SPANISH = (
    "El precio del pan volvió a subir este año, y no es la primera vez que la gente de este "
    "pueblo tiene que pagar más por menos. ¿Qué haría usted para cambiarlo?"
)


def shares(*texts: str | None) -> list[float | None]:
    return language.english_shares(pa.array(texts, type=pa.string()))


def test_an_english_text_is_made_of_common_english_words_in_good_part() -> None:
    (share,) = shares(ENGLISH)
    assert share > 4 * language.MIN_ENGLISH


@pytest.mark.parametrize(
    "text",
    [SPANISH, "Цена на хлеб снова выросла в этом году.", "Le prix du pain monte encore, hélas."],
)
def test_a_text_in_another_language_has_almost_none(text: str) -> None:
    (share,) = shares(text)
    assert share < language.MIN_ENGLISH


def test_the_share_counts_words_not_letters_inside_other_words() -> None:
    assert shares("theme other within bother") == [0.0]
    assert shares("THE Of anD") == [1.0]
    assert shares("the bread") == [0.5]


def test_an_accented_letter_does_not_end_a_word() -> None:
    # 'not' in 'notícias', 'as' in 'crianças', 'on' in 'onça', 'in' in 'inés' and 'için'.
    assert shares("notícias crianças onça inés için") == [0.0]
    assert shares("café the", "it\u2019s here", "the\u2014end") == [0.5, 0.5, 1.0]


def test_the_least_share_sits_between_a_foreign_and_an_english_text() -> None:
    filler = " ".join(["palabra"] * 24)
    one_in_25, two_in_25 = shares(f"the {filler}", f"the of {filler[8:]}")
    assert (one_in_25, two_in_25) == (0.04, 0.08)
    assert one_in_25 < language.MIN_ENGLISH < two_in_25


def test_a_missing_or_empty_text_has_no_share() -> None:
    assert shares(None, "", "  \n ") == [None, None, None]


def test_only_the_start_of_a_text_is_read() -> None:
    long_spanish = " ".join([SPANISH] * 30)
    assert len(long_spanish) > language.HEAD_CHARS
    spanish_first, english_first = shares(f"{long_spanish} {ENGLISH}", f"{ENGLISH} {long_spanish}")
    assert spanish_first < language.MIN_ENGLISH
    assert english_first > language.MIN_ENGLISH
