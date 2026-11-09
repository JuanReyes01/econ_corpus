"""Used by steps 2, 3b, 4 and 5 of the pipeline: read the people named in one part of a byline.

Input: one part of a byline, as cut at ';' (for example 'Doe, Jane Q' or 'Jane Doe is a
columnist in Springfield').
Output: the persons it names and how they were read ('as_written' or 'recovered').

Lives here: recovering a full name from a part that goes on with other text (a town, a role,
a note, a list of co-authors, the members of an editorial board). Does not live here:
deciding whether a text is a name (authors), or cutting a byline into parts and putting
their names together (bylines).

A part is first read as written. If that fails, a full name at its start is recovered
('Jane Doe. Springfield', 'Jane Doe is a columnist'); one word is never taken as a name. A
part with no full name (an institution, a sentence) names nobody, and so does a note that
someone did not write ('Jane Doe is on vacation').
"""

import difflib
import itertools
import re

from econ_corpus.names import authors
from econ_corpus.names.authors import Name
from econ_corpus.names.name_words import HONORIFICS, SAINTS, SENTENCE_WORDS, SUFFIXES

JOINER_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)
# Separators of a list of names; ', and' is one separator, not two.
LIST_RE = re.compile(r",(?:\s*(?:and|&)\s+)?|\s+(?:and|&)\s+", re.IGNORECASE)
# What ends a name that other text follows: a comma, a dash, or a digit that does not start
# an ordinal suffix ('Jane Doe 3d').
NAME_END_RE = re.compile(r",|\s-\s|\d(?!(?:d|nd|rd|th)\b)")
# A label that the export left on the name: 'Jane DoeGuest essay', 'essay, Jane DoeGuest',
# 'Jane Doe Guest essay'.
GLUED_RE = re.compile(
    r"^essay,\s*(?=.*Guest$)|\s*(?:Gue ?st|Reader) essay\b|(?<=[a-z])(?:Guest|Reader)(?: essay)?\b"
)
# What follows the name of someone who did not write: 'is on vacation', 'is off today',
# 'is on book leave', 'is on' (cut short).
ABSENT_RE = re.compile(
    r"(?:is|are) (?:off\b|away\b|on\.?$"
    r"|on (?:an? )?(?:\w+ )?(?:v ?acation|leave|tour|assignment|sabbatical|holiday))",
    re.IGNORECASE,
)
CREDIT_RE = re.compile(r"\bcontributed (?:reporting|research)\b", re.IGNORECASE)
# A period glued to the word after it ('Jane Q.Doe', "Jane Q.O'Doe", 'Jane Doe.These are'),
# but not the periods between initials ('J.Q.', 'M.D').
PERIOD_GLUED_RE = re.compile(r"(?<=[^\W\d_]\.)(?=[^\W\d_](?:[^\W\d_]|['\u2019]))")
SUFFIX_GLUED_RE = re.compile(r"(?<=[a-z])(Jr|Sr)\b")  # 'Jane DoeJr'
# The note of an item written by members of an editorial board, who are named around it.
BOARD_RE = re.compile(
    r"(?:written by|these are (?:the )?personal views of) members of the editorial board",
    re.IGNORECASE,
)
# The period that ends the sentence of one board member: after a word or an ordinal
# ('Jane Doe 3d.'), not after an initial ('J. Q.') or a saint ('St. John'), and not before
# a comma ('Jane Doe Jr., Richard Roe').
BOARD_END_RE = re.compile(r"(?<!\b[Ss][Tt])(?:(?<=[^\W\d_]{2})|(?<=\d[a-z]))\.+(?!\s*,)\s*")
BOARD_LIST = 3  # names that make a list with no 'and' ('Jane Doe, Oak Park' is no list)
LEAD_RE = re.compile(
    r"^(?:(?:and|&)\s+)?(?:by\s+)?", re.IGNORECASE
)  # 'And Jane Doe', 'By Jane Doe'
MIN_ALIKE = 0.8  # share of letters two given names must share to be one name misspelt
SENTENCE_END_RE = re.compile(r"\.['\"\u201d\u2019]*$")  # a period, and quotes closing after it


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
        if authors.abbreviation(word) in SUFFIXES:
            words.append(word)  # '3d' has no capital and 'Jr.' ends no sentence
            continue
        if not authors.has_capital(word) and not authors.is_particle(word):
            return words, text[i:]
        if word.endswith(authors.POSSESSIVES):
            return [*words, word[:-2]], []
        abbreviated = authors.abbreviation(word)
        closes = word.endswith(".") and not authors.INITIALS_RE.fullmatch(word)
        # A title is no end only before the name ('Sen. Jane Doe'); after it, a word such as
        # 'BISHOP.' is a family name that ends a sentence.
        before_name = all(authors.abbreviation(w) in HONORIFICS for w in words)
        title = abbreviated in HONORIFICS and before_name
        if closes and not title and abbreviated not in SAINTS and abbreviated not in SUFFIXES:
            return [*words, word[:-1]], []
        words.append(word)
    return words, []


def is_note(part: str) -> bool:
    """Tell whether a part says that the people it names did not write this article.

    'Jane Doe is on vacation.' is printed under another columnist's article; so are
    'Jane Doe and Ann Roe are on vacation.' and a credit for reporting or research.
    """
    *before, last = JOINER_RE.split(part)
    words, rest = _leading(last)
    named = bool(words) and all(authors.given_first(piece.strip()) for piece in before)
    return bool(CREDIT_RE.search(part)) or (named and bool(ABSENT_RE.match(" ".join(rest))))


def _leading_name(part: str) -> Name | None:
    """Read a full name at the start of a part that goes on with other text.

    A name written twice in a row is read once. A name followed by a small word that does
    not start a sentence, and then by nothing or only by capitalised words, is not read: the
    small word may be a piece of the name cut off by a stray space ('Jane Do e Roe',
    'Jane Do rgan'), so the part is left for the manual review.
    """
    words, rest = _leading(part)
    broken = (
        bool(rest)
        and rest[0].isalpha()
        and rest[0] not in SENTENCE_WORDS
        and all(authors.has_capital(word) for word in rest[1:])
    )
    if broken:
        return None
    half = len(words) // 2
    if half and list(map(authors.lookup, words[:half])) == list(map(authors.lookup, words[half:])):
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


def after_sentence(part: str) -> list[Name]:
    """Read the names that follow the end of a sentence about them ('Committee., Jane Doe').

    The export moves the last word of the whole byline before its first name. That word ends
    a note about the authors, or a note about someone else that follows their names:
    'Jane Doe; Ann Roe is on vacation.' comes out as 'vacation., Jane Doe; Ann Roe is on', so
    the name after the moved word is always an author.
    """
    head, _, rest = part.partition(",")
    last = authors.lookup(SENTENCE_END_RE.sub("", head).split()[-1]) if head.strip(". ") else ""
    closes = SENTENCE_END_RE.search(head) and not authors.is_title(head.strip())
    if not closes or not last or last in SUFFIXES:
        return []
    names = [authors.given_first(piece.strip()) for piece in JOINER_RE.split(rest)]
    return [name for name in names if name] if all(names) else []


def _listed(part: str) -> list[Name]:
    """Read a list of names, with or without an affiliation after it.

    'Jane Doe, Richard Roe and Ann Poe' is three people. In 'Jane Doe and Richard Roe,
    Example Staff' the tail is no name and is left out; that needs 'and' or '&' before the
    last name, since 'Jane Doe, Springfield Heights, Ill.' is one person and her town.
    """
    pieces = [piece.strip() for piece in LIST_RE.split(part)]
    names = [authors.given_first(piece) for piece in pieces]
    run = list(itertools.takewhile(bool, names))
    if len(run) < 2 or any(names[len(run) :]):  # noqa: PLR2004 (a list has two names)
        return []
    # 'and' stands before the last name of the list or right after it ('A, B and Example').
    separators = [text.strip() for text in LIST_RE.findall(part)][len(run) - 2 : len(run)]
    if len(run) < len(names) and all(text == "," for text in separators):
        return []
    # 'Jane Doe and Richard Roe Jane Doe and Richard Roe are ...': the list written again
    # starts in the last name of the run, which then ends in the first name of the list, and
    # the text after it starts with that last name again, in the same or another form
    # ('Dr. Richard Roe', 'R. Roe', 'Richard Row'). 'Mary Jo Ann Lee' after 'Ann Lee', with
    # no name after it, is one name.
    first, last = (f"{name.given} {name.family}" for name in (run[0], run[-1]))
    cut = authors.given_first(last.removesuffix(first)) if last.endswith(f" {first}") else None
    again = _leading_name("".join(pieces[len(run) :][:1]))
    twice = cut and again and (_same_family(cut, again) or same_given(cut, again))
    return [*run[:-1], cut if cut and twice else run[-1]]


def _board_members(part: str) -> list[Name]:
    """Read the names around the note of an editorial-board item.

    'Jane Doe. Richard Roe. Written by members of the editorial board.' lists the members
    who wrote it before or after the note, one sentence each or as a list in one sentence
    ('Jane Doe, Richard Roe and Ann Poe. Written by ...').
    """
    if not BOARD_RE.search(part):
        return []
    found: list[Name] = []
    for sentence in BOARD_END_RE.split(BOARD_RE.sub(".", part)):
        names = [authors.given_first(piece.strip(". ")) for piece in LIST_RE.split(sentence)]
        run = list(itertools.takewhile(bool, names))
        # After one name and a comma comes her town or her role, unless the sentence is a
        # list: it has 'and', or three names.
        plain = all(text == "," for text in LIST_RE.findall(sentence)[: len(run) - 1])
        found += run[:1] if plain and len(run) < BOARD_LIST else run
    return found


def recover_names(part: str) -> list[Name]:
    """Return the persons in a part that `authors.parse_name` cannot read as written.

    The part is a list of names ('Jane Doe, Richard Roe and Ann Poe'), or names after the
    end of a sentence about them, or co-authors scrambled by the export, or it starts with a
    full name followed by other text.
    """
    board = _board_members(part)
    if board:
        return board
    listed = _listed(part)
    if listed:
        return listed
    moved = after_sentence(part)
    if moved:
        return moved
    put_back = unscrambled(part)
    if put_back:
        return put_back
    name = _leading_name(part)
    return [name] if name else []


def read_part(part: str) -> tuple[list[Name], str]:
    """Return the persons a part names and how they were read: 'as_written' or 'recovered'."""
    part = SUFFIX_GLUED_RE.sub(r" \1", PERIOD_GLUED_RE.sub(" ", GLUED_RE.sub("", part)))
    part = LEAD_RE.sub("", part.strip())
    if is_note(part):
        return [], ""
    name = authors.parse_name(part)
    if name:
        return [name], "as_written"
    names = recover_names(part)
    return names, "recovered" if names else ""


def _same_family(name: Name, other: Name) -> bool:
    return authors.fold(name.family) == authors.fold(other.family)


def same_given(name: Name, earlier: Name) -> bool:
    """Tell whether two first given names are forms or misspellings of one name.

    One starts the other ('Tim', 'Timothy') or most of their letters agree ('Thmas',
    'Thomas'). 'Jane' and 'John' are two people of one family.
    """
    one, other = (authors.fold(n.given.split()[0]) for n in (name, earlier))
    alike = difflib.SequenceMatcher(None, one, other).ratio() >= MIN_ALIKE
    return one.startswith(other) or other.startswith(one) or alike
