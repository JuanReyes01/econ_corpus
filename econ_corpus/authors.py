"""Used by steps 2, 4 and 5 of the pipeline: read a person's name.

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
    SAINTS,
    SUFFIXES,
)


class Name(NamedTuple):
    """A person's name as written, split into its pieces."""

    given: str
    family: str
    suffix: str


WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2019.\-][^\W\d_]+)*\.?")  # letters, with ' - . inside
BY_RE = re.compile(r"^(?:[Bb][Yy]\s+|By(?=[A-Z][a-z]))")  # 'By Jane Doe', 'ByJane Doe'
# Capitals after a prefix that is not in capitals: 'McDOE', 'DeDOE', "d'DOE", 'El-DOE'.
MC_RE = re.compile(r"(Ma?c|De|Di|Du|La|Le|[A-Z]?[a-z]+['\u2019\-])([A-Z][A-Z'\u2019\-]+)")
POSSESSIVES = ("'s", "\u2019s")
MIN_SHOUTED = 3  # letters a word in capitals needs to be a name, not initials ('JD')
VOWELS = set("aeiouy")
# 'J.' or 'J.Q.R.', and a name cut to 'McC.': a period that ends no sentence.
INITIALS_RE = re.compile(r"(?:[^\W\d_]\.)+|Ma?c[A-Z]\.")
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


def is_title(text: str) -> bool:
    """Tell whether a text is a title or initials, which can stand where a family name goes."""
    return abbreviation(text) in HONORIFICS or bool(INITIALS_RE.fullmatch(text))


def is_particle(word: str) -> bool:
    """Tell whether a word is a particle of a family name ('van', 'de', 'Del').

    A few particles are far more often a given name when written with a capital ('Al Doe');
    'St.' is one only with its capital.
    """
    bare = lookup(word)
    if bare in SAINTS:
        return word[0].isupper()
    return bare in PARTICLES and (word[0].islower() or bare not in GIVEN_WHEN_CAPITAL)


def has_capital(word: str) -> bool:
    """Tell whether a word has a capital letter, at its start or inside ('al-Doe', 'deDoe')."""
    return any(c.isupper() for c in word)


def _has_org_word(words: list[str]) -> bool:
    """Tell whether a word, or a piece of a hyphenated one, marks an institution."""
    return any(piece in ORG_WORDS for w in words for piece in lookup(w).split("-"))


def _are_name_words(tokens: list[str]) -> bool:
    """Check that every word looks like part of a name.

    A final period is accepted only on initials and on 'St.', so a word that ends a sentence
    ('Doe. Springfield') is not; neither is a possessive ("Doe's").
    """
    return all(
        WORD_RE.fullmatch(t)
        and not t.endswith(POSSESSIVES)
        and (not t.endswith(".") or INITIALS_RE.fullmatch(t) or lookup(t) in SAINTS)
        for t in tokens
    )


def _drop_honorifics(tokens: list[str]) -> list[str]:
    while tokens and abbreviation(tokens[0]) in HONORIFICS:
        tokens = tokens[1:]
    return tokens


def given_first(text: str, suffix: str = "") -> Name | None:
    """Read 'Given Family', optionally with a suffix as the last word or given apart."""
    tokens = _drop_honorifics(text.split())
    while len(tokens) > 2 and lookup(tokens[-1]) in DEGREES:  # noqa: PLR2004 ('Jane Doe MD')
        tokens = tokens[:-1]
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
    # 'Le Monde' is not a person, and one letter is not a family name ('Jane Z').
    if all(lookup(t) in ARTICLES for t in tokens[:start]) or len(lookup(tokens[-1])) == 1:
        return None
    return Name(" ".join(tokens[:start]), " ".join(tokens[start:]), suffix)


def _family_first(family: str, given: str, suffix: str) -> Name | None:
    """Read 'Family, Given', the form ProQuest writes for most authors."""
    given = BY_RE.sub("", given)  # 'DOE, By JANE'
    if is_title(family):
        # A title or a state where the family name goes ('Sen, Jane Doe', 'N.J., Jane Doe'):
        # the name is what follows, if it reads as one. Initials alone are never a family
        # name ('E., Jane'); a title can be one ('Sen, Jane').
        moved = given_first(given, suffix)
        if moved or INITIALS_RE.fullmatch(family):
            return moved
    family_words, given_words = family.split(), _drop_honorifics(given.split())
    last_family = abbreviation(family_words[-1]) if family_words else ""
    one_family_name = all(is_particle(word) for word in family_words[:-2])
    if last_family in SUFFIXES and not suffix and one_family_name:
        # 'Doe Jr., John', and 'III, John Q Doe' where the suffix alone was moved in front.
        # Not 'Jane Doe Jr., Richard Roe', which is two names.
        suffix, family_words = SUFFIXES[abbreviation(family_words[-1])], family_words[:-1]
        if not family_words:
            return given_first(given, suffix)
    # 'Doe, John Jr.': the suffix follows the given names. Not in 'Jane Doe, Richard Roe Jr.',
    # two names, where more than a family name stands before the comma.
    twice = len(given_words) > 1 and [lookup(given_words[-1])] == list(
        map(lookup, family_words[-1:])
    )
    if twice:  # 'Doe, Jane Doe': the family name written again after the given names
        given_words = given_words[:-1]
    alone = all(is_particle(word) for word in family_words[:-1])
    last = abbreviation(given_words[-1]) if len(given_words) > 1 else ""
    if not suffix and alone and last in SUFFIXES:
        suffix, given_words = SUFFIXES[last], given_words[:-1]
    # 'Springfield, JANE DOE' is a town before a name in capitals, not 'Family, Given'.
    shouted = [w for w in given_words if w.isupper() and sum(c.isalpha() for c in w) > 1]
    town = len(shouted) > 1 and not any(_in_capitals(word) for word in family_words)
    if town or not 1 <= len(family_words) <= MAX_FAMILY or not 1 <= len(given_words) <= MAX_GIVEN:
        return None
    # One word before the comma can be a family name that is also an institution word
    # ('Press, Jane'); several words holding one ('The Times, London') are an institution.
    # 'and' among the given names means two people ('Doe, Jane Roe and Ann').
    refused = (
        not _are_name_words(family_words + given_words)
        or lookup(family) in ROLE_WORDS | SAINTS  # 'Staff, Jane', 'St, Jane'
        or "and" in map(lookup, given_words)
        or _has_org_word(given_words)
        or (len(family_words) > 1 and _has_org_word(family_words))
        or not given_words[0][0].isupper()
        or not any(has_capital(t) for t in family_words)
    )
    return None if refused else Name(" ".join(given_words), " ".join(family_words), suffix)


def parse_name(part: str) -> Name | None:
    """Return the person a part names, or None if it is not clearly a person's name."""
    sides = [side.strip() for side in part.split(",")]
    suffix = ""

    def named() -> bool:
        """Tell whether what stands before the last side is already a whole name."""
        return len(sides) > 2 or len(sides[0].split()) > 1  # noqa: PLR2004

    # 'Doe, Jane, M.D.' and 'Jane Doe, MD' end in a degree. In 'Doe, JD' the JD can be the
    # initials of the given names, but only in capitals: 'Doe, Rn' is a degree.
    while (
        len(sides) > 1
        and sides[-1]
        and all(lookup(t) in DEGREES for t in sides[-1].split())
        and (named() or not sides[-1].isupper())
    ):
        sides = sides[:-1]
    # 'Doe, John, Jr' and 'John Doe, Jr' end in a suffix; in 'Doe, JR' the JR is a given name.
    if named() and abbreviation(sides[-1]) in SUFFIXES:
        suffix, sides = SUFFIXES[abbreviation(sides[-1])], sides[:-1]
    if len(sides) == 1:
        return given_first(sides[0], suffix)
    if len(sides) == 2:  # noqa: PLR2004
        return _family_first(sides[0], sides[1], suffix)
    return None


def reviewed_name(part: str) -> Name | None:
    """Read 'Family, Given' or 'Family, Given, Suffix' as a reviewer wrote it.

    None of the checks that guard against institutions apply: a person decided this is a
    name, so 'Red Star, Jane' and 'Doe, Jane 8.' are taken as written. Each side still needs
    a letter: 'Doe, -' is a slip of the reviewer, not a name.
    """
    sides = [side.strip() for side in part.split(",")]
    suffix = ""
    if len(sides) == 3 and abbreviation(sides[2]) in SUFFIXES:  # noqa: PLR2004
        suffix, sides = SUFFIXES[abbreviation(sides[2])], sides[:2]
    lettered = all(any(c.isalpha() for c in side) for side in sides)
    return Name(sides[1], sides[0], suffix) if len(sides) == 2 and lettered else None  # noqa: PLR2004


def _in_capitals(word: str) -> bool:
    return word.isupper() or bool(MC_RE.fullmatch(word))


def _normal_case(word: str) -> str:
    """Give normal casing to a word in capitals: O'DOE-ROE is O'Doe-Roe, McDOE is McDoe."""
    mc = MC_RE.fullmatch(word)
    if mc:
        return mc[1] + _normal_case(mc[2])
    cased = re.sub(r"[^\W\d_]+", lambda m: m[0].capitalize(), word)
    cased = re.sub(r"^Mc([a-z])(?=[a-z]{2})", lambda m: "Mc" + m[1].upper(), cased)  # 'MCDOE'
    return re.sub("(['\u2019])S$", r"\1s", cased)  # a possessive keeps its small s


def display(name: Name) -> str:
    """Return the name given-name first, with normal casing for what was written in capitals.

    In a name all in capitals every word is fixed. In any other name only a word that is
    clearly not initials is: three or more capitals with a vowel ('JANE'), or capitals after
    a prefix ('DeDOE'). Other capitals stay ('JD Doe', 'JQD Doe').
    """
    words = f"{name.given} {name.family}".split()
    # Lower-case particles ('del') do not count when deciding that a name is in capitals.
    shouted = all(_in_capitals(w) for w in words if not (w.islower() and is_particle(w)))

    def fix(word: str) -> bool:
        letters = [c for c in fold(word) if c.isalpha()]
        spoken = len(letters) >= MIN_SHOUTED and bool(VOWELS & set(letters))
        numeral = word in SUFFIXES.values()  # 'III' stays
        capitals = "." not in word and _in_capitals(word) and not numeral
        return capitals and (shouted or spoken or not word.isupper())

    words = [_normal_case(w) if fix(w) else w for w in words]
    return " ".join([*words, name.suffix]).strip()


def fold(text: str) -> str:
    """Return the letters and digits of a text, casefolded and without accents."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text.casefold() if c.isalnum())


def one_edit(a: str, b: str) -> bool:
    """Tell whether one letter added, dropped or changed, or two neighbours swapped, gives b."""
    if len(a) > len(b):
        a, b = b, a
    i = next((k for k, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), len(a))
    if len(a) < len(b):
        return a[i:] == b[i + 1 :]
    swapped = a[i : i + 2] == b[i : i + 2][::-1] and a[i + 2 :] == b[i + 2 :]
    return a[i + 1 :] == b[i + 1 :] or swapped


def name_key(name: Name) -> str:
    """Return a key equal for spelling variants of one name.

    Case, accents, periods, apostrophes, hyphens and spaces are ignored, so 'DOE, JANE Q.',
    'Jane Q Doe' and 'D oe, Jane Q' (a stray space from ProQuest) share a key. Middle names
    and suffixes are kept: deciding that 'John Doe' and 'John Doe Jr' are one person is
    not done here.
    """
    return fold(f"{name.given}{name.family}{name.suffix}")
