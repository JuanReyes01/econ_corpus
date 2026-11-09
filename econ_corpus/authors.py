"""Stage 4 of the pipeline: read a person's name.

Input: one name as written in a byline ('Doe, Jane Q' or 'Jane Q. Doe').
Output: a `Name` (given names, family name, suffix), or None if the text is not clearly a
person's name; and for a `Name`, a display form ('Jane Q Doe') and a key that is equal for
spelling variants of one name.

Lives here: deciding whether a text is a name, its pieces, the display form and the key.
Does not live here: splitting a byline into authors or recovering a name from longer text
(bylines), or deciding that two different keys are the same person (identity).
"""

import re
from typing import NamedTuple
import unicodedata

from econ_corpus.name_words import (
    ARTICLES,
    DEGREES,
    GIVEN_WHEN_CAPITAL,
    HONORIFICS,
    ORG_WORDS,
    PARTICLES,
    ROLE_WORDS,
    SUFFIXES,
)


class Name(NamedTuple):
    """A person's name as written, split into its pieces."""

    given: str
    family: str
    suffix: str


WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2019.\-][^\W\d_]+)*\.?")  # letters, with ' - . inside
INITIALS_RE = re.compile(r"(?:[^\W\d_]\.)+")  # 'J.' or 'J.Q.R.'
MAX_NATURAL, MAX_FAMILY, MAX_GIVEN = 5, 3, 4  # most words a name, or one side of it, may have


def lookup(token: str) -> str:
    """Return a word without periods and casefolded, for looking it up in the word lists."""
    return token.replace(".", "").casefold()


def abbreviation(token: str) -> str:
    """Return a word as a title or suffix would be looked up: casefolded, no final period.

    Initials written with periods inside ('M.R.', 'J.R.') are never a title or a suffix, so
    they give an empty string.
    """
    stem = token.rstrip(".")
    return "" if "." in stem else stem.casefold()


def is_particle(word: str) -> bool:
    """Tell whether a word is a particle of a family name ('van', 'de', 'Del').

    A few particles are far more often a given name when written with a capital ('Al Doe').
    """
    bare = lookup(word)
    return bare in PARTICLES and (word[0].islower() or bare not in GIVEN_WHEN_CAPITAL)


def has_capital(word: str) -> bool:
    """Tell whether a word has a capital letter, at its start or inside ('al-Doe', 'deDoe')."""
    return any(c.isupper() for c in word)


def _has_org_word(words: list[str]) -> bool:
    """Tell whether a word, or a piece of a hyphenated one, marks an institution."""
    return any(piece in ORG_WORDS for w in words for piece in lookup(w).split("-"))


def _are_name_words(tokens: list[str]) -> bool:
    """Check that every word looks like part of a name.

    A final period is accepted only on initials, so a word that ends a sentence
    ('Doe. Springfield') is not.
    """
    return all(
        WORD_RE.fullmatch(t) and (not t.endswith(".") or INITIALS_RE.fullmatch(t)) for t in tokens
    )


def _drop_honorifics(tokens: list[str]) -> list[str]:
    while tokens and abbreviation(tokens[0]) in HONORIFICS:
        tokens = tokens[1:]
    return tokens


def given_first(text: str, suffix: str = "") -> Name | None:
    """Read 'Given Family', optionally with a suffix as the last word or given apart."""
    tokens = _drop_honorifics(text.split())
    if tokens and not suffix and abbreviation(tokens[-1]) in SUFFIXES:
        suffix, tokens = SUFFIXES[abbreviation(tokens[-1])], tokens[:-1]
    if not 2 <= len(tokens) <= MAX_NATURAL or not _are_name_words(tokens):  # noqa: PLR2004
        return None
    capitals = tokens[0][0].isupper() and all(has_capital(t) for t in tokens if not is_particle(t))
    if _has_org_word(tokens) or not capitals:
        return None
    # The family name is the last word plus the particles right before it.
    start = len(tokens) - 1
    while start > 1 and is_particle(tokens[start - 1]):
        start -= 1
    if all(lookup(t) in ARTICLES for t in tokens[:start]):  # 'Le Monde' is not a person
        return None
    return Name(" ".join(tokens[:start]), " ".join(tokens[start:]), suffix)


def _family_first(family: str, given: str, suffix: str) -> Name | None:
    """Read 'Family, Given', the form ProQuest writes for most authors."""
    family_words, given_words = family.split(), _drop_honorifics(given.split())
    if not 1 <= len(family_words) <= MAX_FAMILY or not 1 <= len(given_words) <= MAX_GIVEN:
        return None
    if not _are_name_words(family_words + given_words):
        return None
    if all(lookup(t) in DEGREES for t in given_words) or lookup(family) in ROLE_WORDS:
        return None
    # One word before the comma can be a family name that is also an institution word
    # ('Press, Jane'); several words holding one ('The Times, London') are an institution.
    if _has_org_word(given_words) or (len(family_words) > 1 and _has_org_word(family_words)):
        return None
    if not given_words[0][0].isupper() or not any(has_capital(t) for t in family_words):
        return None
    return Name(" ".join(given_words), " ".join(family_words), suffix)


def parse_name(part: str) -> Name | None:
    """Return the person a part names, or None if it is not clearly a person's name."""
    sides = [side.strip() for side in part.split(",")]
    suffix = ""
    # 'Doe, John, Jr' and 'John Doe, Jr' end in a suffix; in 'Doe, JR' the JR is a given name.
    names_before = len(sides) > 2 or len(sides[0].split()) > 1  # noqa: PLR2004
    if names_before and abbreviation(sides[-1]) in SUFFIXES:
        suffix, sides = SUFFIXES[abbreviation(sides[-1])], sides[:-1]
    if len(sides) == 1:
        return given_first(sides[0], suffix)
    if len(sides) == 2:  # noqa: PLR2004
        return _family_first(sides[0], sides[1], suffix)
    return None


def reviewed_name(part: str) -> Name | None:
    """Read 'Family, Given' or 'Family, Given, Suffix' as a reviewer wrote it.

    None of the checks that guard against institutions apply: a person decided this is a
    name, so 'Red Star, Jane' and 'Doe, Jane 8.' are taken as written.
    """
    sides = [side.strip() for side in part.split(",")]
    suffix = ""
    if len(sides) == 3 and abbreviation(sides[2]) in SUFFIXES:  # noqa: PLR2004
        suffix, sides = SUFFIXES[abbreviation(sides[2])], sides[:2]
    if len(sides) != 2 or not all(sides):  # noqa: PLR2004
        return None
    return Name(sides[1], sides[0], suffix)


def _normal_case(word: str) -> str:
    """Capitalise each run of letters of a word in capitals: O'DOE-ROE gives O'Doe-Roe."""
    cased = re.sub(r"[^\W\d_]+", lambda m: m[0].capitalize(), word)
    return re.sub("(['\u2019])S$", r"\1s", cased)  # a possessive keeps its small s


def display(name: Name) -> str:
    """Return the name given-name first; a name written in capitals gets normal casing."""
    words = f"{name.given} {name.family}".split()
    # Lower-case particles ('del') do not count when deciding that a name is in capitals.
    if all(w.isupper() for w in words if not (w.islower() and is_particle(w))):
        words = [w if "." in w or not w.isupper() else _normal_case(w) for w in words]
    return " ".join([*words, name.suffix]).strip()


def fold(text: str) -> str:
    """Return the letters and digits of a text, casefolded and without accents."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text.casefold() if c.isalnum())


def name_key(name: Name) -> str:
    """Return a key equal for spelling variants of one name.

    Case, accents, periods, apostrophes, hyphens and spaces are ignored, so 'DOE, JANE Q.',
    'Jane Q Doe' and 'D oe, Jane Q' (a stray space from ProQuest) share a key. Middle names
    and suffixes are kept: deciding that 'John Doe' and 'John Doe Jr' are one person is
    not done here.
    """
    return fold(f"{name.given}{name.family}{name.suffix}")
