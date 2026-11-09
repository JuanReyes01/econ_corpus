"""Stage 4b of the pipeline: read the people named in a ProQuest byline.

Input: the `author` value of a record, as exported (for example 'Doe, Jane Q; Roe, Richard').
Output: the persons it names, in order, each once, with how each was read.

Lives here: splitting a byline into parts, recovering a full name from a part that goes on
with other text, and applying the corrections of the manual review. Does not live here:
deciding whether a text is a name (authors) or the review files themselves (review).

A part is first read as written. If that fails, a full name at its start is recovered
('Jane Doe. Springfield', 'Jane Doe is a columnist'); one word is never taken as a name. A
part with no full name (an institution, a sentence) names nobody.
"""

import re

from econ_corpus import authors
from econ_corpus.authors import Name
from econ_corpus.name_words import HONORIFICS, SUFFIXES

JOINER_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)
LIST_RE = re.compile(r",|\s+(?:and|&)\s+", re.IGNORECASE)  # separators of a list of names
NAME_END_RE = re.compile(r",|\s-\s|\d")  # what ends a name that other text follows
POSSESSIVES = ("'s", "\u2019s")


def split_authors(raw: str | None) -> list[str]:
    """Split a byline into parts, one per author as written.

    ';' separates authors. A suffix standing alone ('Doe, John; Jr.') belongs to the name
    before it, and so does a given name cut off from its one-word family name ('Doe; , Jane').
    A part without a comma loses a leading 'By' and is split at 'and' or '&'.
    """
    parts: list[str] = []
    for piece in (raw or "").split(";"):
        text = piece.strip()
        if not text:
            continue
        if authors.abbreviation(text) in SUFFIXES and parts:
            parts[-1] = f"{parts[-1]}, {SUFFIXES[authors.abbreviation(text)]}"
        elif text.startswith(",") and parts and authors.WORD_RE.fullmatch(parts[-1]):
            parts[-1] = f"{parts[-1]}{text}"  # 'Doe; , Jane' is 'Doe, Jane' cut in two
        elif "," in text:
            parts.append(text)
        else:
            parts += [p.strip() for p in JOINER_RE.split(authors.BY_RE.sub("", text)) if p.strip()]
    return parts


def _leading_name(part: str) -> Name | None:
    """Read a full name at the start of a part that goes on with other text.

    The name ends at a comma, a dash, a digit, a word that closes a sentence, a possessive
    or the first lower-case word. A name written twice in a row is read once.
    """
    words: list[str] = []
    for word in NAME_END_RE.split(authors.BY_RE.sub("", part.strip()), maxsplit=1)[0].split():
        if not any(c.isalnum() for c in word):
            continue  # a stray period or dash inside the name
        if not authors.has_capital(word) and not authors.is_particle(word):
            break
        if word.endswith(POSSESSIVES):
            words.append(word[:-2])
            break
        ends_sentence = word.endswith(".") and not authors.INITIALS_RE.fullmatch(word)
        if (
            ends_sentence
            and authors.abbreviation(word) not in HONORIFICS
            and authors.abbreviation(word) not in SUFFIXES
        ):
            words.append(word[:-1])
            break
        words.append(word)
    half = len(words) // 2
    if half and [w.casefold() for w in words[:half]] == [w.casefold() for w in words[half:]]:
        words = words[:half]
    return authors.given_first(" ".join(words))


def _unscrambled(part: str) -> list[Name]:
    """Put back co-authors that the export scrambled around the last family name.

    'Jane Roe and Ann Doe' is exported as 'Doe, Jane Roe and Ann': the family name of the
    last author comes first, and her given name is left at the end.
    """
    family, _, rest = part.partition(",")
    pieces = [piece.strip() for piece in LIST_RE.split(rest)]
    others = [authors.given_first(piece) for piece in pieces[:-1]]
    last = authors.parse_name(f"{family.strip()}, {pieces[-1]}")
    return [*others, last] if others and last and all(others) else []


def recover_names(part: str) -> list[Name]:
    """Return the persons in a part that `authors.parse_name` cannot read as written.

    The part is a list of names ('Jane Doe, Richard Roe and Ann Poe'), or co-authors scrambled
    by the export, or it starts with a full name followed by other text.
    """
    listed = [authors.given_first(piece.strip()) for piece in LIST_RE.split(part)]
    if len(listed) > 1 and all(listed):
        return [name for name in listed if name]
    unscrambled = _unscrambled(part)
    if unscrambled:
        return unscrambled
    name = _leading_name(part)
    return [name] if name else []


def read_part(part: str) -> tuple[list[Name], str]:
    """Return the persons a part names and how they were read: 'as_written' or 'recovered'."""
    name = authors.parse_name(part)
    if name:
        return [name], "as_written"
    names = recover_names(part)
    return names, "recovered" if names else ""


def read_byline(
    raw: str | None, corrections: dict[str, str] | None = None
) -> list[tuple[Name, str]]:
    """Return the persons a byline names, in order, each once, with how each was read.

    A part listed in `corrections` (decisions of the manual review) is read from its corrected
    byline and marked 'manual_review'; the others are 'as_written' or 'recovered'.
    """
    found: dict[str, tuple[Name, str]] = {}
    for part in split_authors(raw):
        if corrections and part in corrections:
            reviewed = (authors.reviewed_name(p) for p in corrections[part].split(";"))
            names = [name for name in reviewed if name]
            how = "manual_review"
        else:
            names, how = read_part(part)
        for name in names:
            found.setdefault(authors.name_key(name), (name, how))
    return list(found.values())


def people(raw: str | None, corrections: dict[str, str] | None = None) -> list[Name]:
    """Return the persons a byline names, in order, each once."""
    return [name for name, _ in read_byline(raw, corrections)]


def is_signed(raw: str | None) -> bool:
    """Tell whether a byline has anything other than ProQuest's 'Anonymous' marker."""
    return any(
        p.strip() and authors.lookup(p.strip()) != "anonymous" for p in (raw or "").split(";")
    )
