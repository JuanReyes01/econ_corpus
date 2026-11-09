"""Used by steps 2, 3b, 4 and 5 of the pipeline: read the name at the start of a byline part.

Input: one part of a byline that may go on with other text after a name ('Jane Doe is a
columnist in Springfield', 'Jane Doe. Springfield').
Output: the words of the name and the words after it, and the full name they read as.

Lives here: where a name at the start of a part ends, and reading it once when it is
written twice. Does not live here: reading a name as written (authors), lists of names and
board members (name_lists), or the order in which a part is tried (parts).
"""

import re

from econ_corpus.names import authors, name_tokens
from econ_corpus.names.authors import Name
from econ_corpus.names.name_words import HONORIFICS, SAINTS, SENTENCE_WORDS, SUFFIXES

# What ends a name that other text follows: a comma, a dash, or a digit that does not start
# an ordinal suffix ('Jane Doe 3d').
NAME_END_RE = re.compile(r",|\s-\s|\d(?!(?:d|nd|rd|th)\b)")


def leading(part: str) -> tuple[list[str], list[str]]:
    """Split the start of a part into the words of a name and the words that go on after it.

    The name ends at a word that closes a sentence, a possessive or the first lower-case
    word; only the text before a comma, a dash or a digit is looked at. What goes on is
    returned only when a lower-case word ended the name: after a sentence or a possessive
    the name is known to be complete.
    """
    text = NAME_END_RE.split(authors.BY_RE.sub("", part.strip()), maxsplit=1)[0].split()
    words: list[str] = []
    for i, word in enumerate(text):
        if not any(c.isalnum() for c in word):
            continue  # a stray period or dash inside the name
        if name_tokens.abbreviation(word) in SUFFIXES:
            words.append(word)  # '3d' has no capital and 'Jr.' ends no sentence
            continue
        if not name_tokens.has_capital(word) and not name_tokens.is_particle(word):
            return words, text[i:]
        if word.endswith(name_tokens.POSSESSIVES):
            return [*words, word[:-2]], []
        abbreviated = name_tokens.abbreviation(word)
        closes = word.endswith(".") and not name_tokens.INITIALS_RE.fullmatch(word)
        # A title is no end only before the name ('Sen. Jane Doe'); after it, a word such as
        # 'BISHOP.' is a family name that ends a sentence.
        before_name = all(name_tokens.abbreviation(w) in HONORIFICS for w in words)
        title = abbreviated in HONORIFICS and before_name
        if closes and not title and abbreviated not in SAINTS and abbreviated not in SUFFIXES:
            return [*words, word[:-1]], []
        words.append(word)
    return words, []


def leading_name(part: str) -> Name | None:
    """Read a full name at the start of a part that goes on with other text.

    A name written twice in a row is read once. A name followed by a small word that does
    not start a sentence, and then by nothing or only by capitalised words, is not read: the
    small word may be a piece of the name cut off by a stray space ('Jane Do e Roe',
    'Jane Do rgan'), so the part is left for the manual review.
    """
    words, rest = leading(part)
    broken = (
        bool(rest)
        and rest[0].isalpha()
        and rest[0] not in SENTENCE_WORDS
        and all(name_tokens.has_capital(word) for word in rest[1:])
    )
    if broken:
        return None
    half = len(words) // 2
    if half and list(map(name_tokens.lookup, words[:half])) == list(
        map(name_tokens.lookup, words[half:])
    ):
        words = words[:half]
    return authors.given_first(" ".join(words))
