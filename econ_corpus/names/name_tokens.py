"""Used by steps 2, 4 and 5 of the pipeline: tell what one word of a byline can be in a name.

Input: one word, or the words of one side of a name, as written in a byline.
Output: whether it is a title or initials, a particle, in capitals, a word of an
institution, or a word that can stand in a name; and the word as it is looked up.

Lives here: the tests on single words that reading a name relies on. Does not live here:
the word lists (name_words), reading a whole name (authors), or its display form and key
(spelling).
"""

import re

from econ_corpus.names.name_words import (
    GIVEN_WHEN_CAPITAL,
    HONORIFICS,
    ORG_WORDS,
    PARTICLES,
    SAINTS,
)

WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2019.\-][^\W\d_]+)*\.?")  # letters, with ' - . inside
# Capitals after a prefix that is not in capitals: 'McDOE', 'DeDOE', "d'DOE", 'El-DOE'.
MC_RE = re.compile(r"(Ma?c|De|Di|Du|La|Le|[A-Z]?[a-z]+['\u2019\-])([A-Z][A-Z'\u2019\-]+)")
POSSESSIVES = ("'s", "\u2019s")
# 'J.' or 'J.Q.R.', and a name cut to 'McC.': a period that ends no sentence.
INITIALS_RE = re.compile(r"(?:[^\W\d_]\.)+|Ma?c[A-Z]\.")


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


def has_org_word(words: list[str]) -> bool:
    """Tell whether a word, or a piece of a hyphenated one, marks an institution."""
    return any(piece in ORG_WORDS for w in words for piece in lookup(w).split("-"))


def are_name_words(tokens: list[str]) -> bool:
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


def drop_honorifics(tokens: list[str]) -> list[str]:
    """Drop the titles at the start of the words of a name (Dr, 'Sen.')."""
    while tokens and abbreviation(tokens[0]) in HONORIFICS:
        tokens = tokens[1:]
    return tokens


def in_capitals(word: str) -> bool:
    """Tell whether a word is written in capitals, also after a prefix ('DOE', 'McDOE')."""
    return word.isupper() or bool(MC_RE.fullmatch(word))
