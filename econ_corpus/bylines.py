"""Used by steps 2 and 4 of the pipeline: read the people named in a ProQuest byline.

Input: the `author` value of a record, as exported (for example 'Doe, Jane Q; Roe, Richard').
Output: the persons it names, in order, each once, with how each was read.

Lives here: splitting a byline into parts, recovering a full name from a part that goes on
with other text, and applying the corrections of the manual review. Does not live here:
deciding whether a text is a name (authors) or the review files themselves (review).

A part is first read as written. If that fails, a full name at its start is recovered
('Jane Doe. Springfield', 'Jane Doe is a columnist'); one word is never taken as a name. A
part with no full name (an institution, a sentence) names nobody, and so does a note that
someone did not write ('Jane Doe is on vacation').
"""

import re

from econ_corpus import authors
from econ_corpus.authors import Name
from econ_corpus.name_words import ABSENT_WORDS, HONORIFICS, SAINTS, SENTENCE_WORDS, SUFFIXES

JOINER_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)
LIST_RE = re.compile(r",|\s+(?:and|&)\s+", re.IGNORECASE)  # separators of a list of names
NAME_END_RE = re.compile(r",|\s-\s|\d")  # what ends a name that other text follows
# A label that the export left on the name: 'Jane DoeGuest essay', 'essay, Jane DoeGuest',
# 'Jane Doe Guest essay'.
GLUED_RE = re.compile(r"^essay,\s*(?=.*Guest$)|\s*Gue ?st essay\b|(?<=[a-z])Guest\b")
# What follows the name of someone who did not write: 'is on vacation', 'is off today',
# 'is on book leave', 'is on' (cut short), 'contributed reporting'.
ABSENT_RE = re.compile(
    r"(?:(?:is|are) (?:off\b|away\b|on\.?$"
    r"|on (?:an? )?(?:\w+ )?(?:vacation|leave|tour|assignment|sabbatical|holiday))"
    r"|contributed (?:reporting|research)\b)",
    re.IGNORECASE,
)
# A period glued to the word after it ('Jane Q.Doe', "Jane Q.O'Doe", 'Jane Doe.These are'),
# but not the periods between initials ('J.Q.', 'M.D').
PERIOD_GLUED_RE = re.compile(r"(?<=[^\W\d_]\.)(?=[^\W\d_](?:[^\W\d_]|['\u2019]))")
BIO_RE = re.compile(r"(?:is|was|are|were|has|had)\b", re.IGNORECASE)  # starts a sentence
SENTENCE_END_RE = re.compile(r"\.['\"\u201d\u2019]*$")  # a period, and quotes closing after it
# 'and Andrew' comes out of the export as 'andrew': 'and' swallowed the start of the name.
AND_GLUED_RE = re.compile(r"(?<=\s)and(?=[a-z]+\s+[A-Z])")


def split_authors(raw: str | None) -> list[str]:
    """Split a byline into parts, one per author as written.

    ';' separates authors. A suffix standing alone ('Doe, John; Jr.') belongs to the name
    before it, and so does a given name cut off from its one-word family name ('Doe; , Jane').
    A part without a comma loses a leading 'By' and is split at 'and' or '&', unless the 'and'
    is inside a sentence about the first author ('Jane Doe is a teacher and ...') or the part
    is a note about people who did not write ('Jane Doe and Ann Roe are on vacation').
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
            text = AND_GLUED_RE.sub("and And", authors.BY_RE.sub("", text))
            pieces = [p.strip() for p in JOINER_RE.split(text) if p.strip()]
            sentence = BIO_RE.match(" ".join(_leading(pieces[0])[1])) if pieces else None
            parts += [text] if sentence or _is_note(text) else pieces
    return parts


def _leading(part: str) -> tuple[list[str], list[str]]:
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
        if not authors.has_capital(word) and not authors.is_particle(word):
            return words, text[i:]
        if word.endswith(authors.POSSESSIVES):
            return [*words, word[:-2]], []
        abbreviated = authors.abbreviation(word)
        closes = word.endswith(".") and not authors.INITIALS_RE.fullmatch(word)
        if closes and abbreviated not in HONORIFICS | SAINTS and abbreviated not in SUFFIXES:
            return [*words, word[:-1]], []
        words.append(word)
    return words, []


def _is_note(part: str) -> bool:
    """Tell whether a part says that the people it names did not write this article.

    'Jane Doe is on vacation.' is printed under another columnist's article; so is
    'Jane Doe and Ann Roe are on vacation.'.
    """
    *before, last = JOINER_RE.split(part)
    words, rest = _leading(last)
    named = bool(words) and all(authors.given_first(piece.strip()) for piece in before)
    return named and bool(ABSENT_RE.match(" ".join(rest)))


def _leading_name(part: str) -> Name | None:
    """Read a full name at the start of a part that goes on with other text.

    A name written twice in a row is read once. A name followed by a small word that does
    not start a sentence, and then only by capitalised words, is not read: the small word
    may be a piece of the name cut off by a stray space ('Jane Do e Roe'), so the part is
    left for the manual review.
    """
    words, rest = _leading(part)
    broken = (
        len(rest) > 1
        and rest[0].isalpha()
        and rest[0] not in SENTENCE_WORDS
        and all(authors.has_capital(word) for word in rest[1:])
    )
    if broken:
        return None
    half = len(words) // 2
    if half and [w.casefold() for w in words[:half]] == [w.casefold() for w in words[half:]]:
        words = words[:half]
    return authors.given_first(" ".join(words))


def unscrambled(part: str) -> list[Name]:
    """Put back co-authors that the export scrambled around the last family name.

    'Jane Roe and Ann Doe' is exported as 'Doe, Jane Roe and Ann': the family name of the
    last author comes first, and her given name is left at the end, after 'and'. A family
    name stands alone before the comma, so 'Jane Doe, Richard Roe and Co' is not this case.
    """
    family, _, rest = part.partition(",")
    separators = LIST_RE.findall(rest)
    alone = all(authors.is_particle(word) for word in family.split()[:-1])
    if not separators or separators[-1] == "," or not alone:
        return []
    pieces = [piece.strip() for piece in LIST_RE.split(rest)]
    others = [authors.given_first(piece) for piece in pieces[:-1]]
    last = authors.parse_name(f"{family.strip()}, {pieces[-1]}")
    return [*others, last] if others and last and all(others) else []


def _after_sentence(part: str) -> list[Name]:
    """Read the names that follow the end of a sentence about them ('Committee., Jane Doe').

    The export moves the last word of a note about the authors before their names. A note
    saying that someone did not write ('vacation., Jane Doe') names nobody; neither does a
    suffix before the comma ('Doe Jr., Jane'), which ends no sentence.
    """
    head, _, rest = part.partition(",")
    last = authors.lookup(SENTENCE_END_RE.sub("", head).split()[-1]) if head.strip(". ") else ""
    closes = SENTENCE_END_RE.search(head) and not authors.is_title(head.strip())
    if not closes or not last or last in ABSENT_WORDS or last in SUFFIXES:
        return []
    names = [authors.given_first(piece.strip()) for piece in JOINER_RE.split(rest)]
    return [name for name in names if name] if all(names) else []


def recover_names(part: str) -> list[Name]:
    """Return the persons in a part that `authors.parse_name` cannot read as written.

    The part is a list of names ('Jane Doe, Richard Roe and Ann Poe'), or names after the
    end of a sentence about them, or co-authors scrambled by the export, or it starts with a
    full name followed by other text.
    """
    listed = [authors.given_first(piece.strip()) for piece in LIST_RE.split(part)]
    if len(listed) > 1 and all(listed):
        return [name for name in listed if name]
    moved = _after_sentence(part)
    if moved:
        return moved
    put_back = unscrambled(part)
    if put_back:
        return put_back
    name = _leading_name(part)
    return [name] if name else []


def read_part(part: str) -> tuple[list[Name], str]:
    """Return the persons a part names and how they were read: 'as_written' or 'recovered'."""
    part = PERIOD_GLUED_RE.sub(" ", GLUED_RE.sub("", part)).strip()
    if _is_note(part):
        return [], ""
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
