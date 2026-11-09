"""Used by steps 2, 3b, 4 and 5 of the pipeline: read the several people named in one part.

Input: one part of a byline that names more than one person ('Jane Doe, Richard Roe and Ann
Poe', 'Doe, Jane Roe and Ann', the members of an editorial board around its note).
Output: the persons it names, or an empty list when it is not such a part.

Lives here: lists of co-authors, co-authors scrambled by the export, the members of an
editorial board, and whether two names share a family name or a first given name. Does not
live here: the name at the start of a part (name_start), or the order in which a part is
tried (parts).
"""

import difflib
import itertools
import re

from econ_corpus.names import authors, name_tokens, spelling
from econ_corpus.names.authors import Name
from econ_corpus.names.name_start import leading_name

# Separators of a list of names; ', and' is one separator, not two.
LIST_RE = re.compile(r",(?:\s*(?:and|&)\s+)?|\s+(?:and|&)\s+", re.IGNORECASE)
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
MIN_ALIKE = 0.8  # share of letters two given names must share to be one name misspelt


def unscrambled(part: str) -> list[Name]:
    """Put back co-authors that the export scrambled around the last family name.

    'Jane Roe and Ann Doe' is exported as 'Doe, Jane Roe and Ann': the family name of the
    last author comes first, and her given name is left at the end, after 'and'. A family
    name stands alone before the comma, so 'Jane Doe, Richard Roe and Co' is not this case.
    """
    family, _, rest = part.partition(",")
    separators = LIST_RE.findall(rest)
    alone = all(name_tokens.is_particle(word) for word in family.split()[:-1])
    if not separators or separators[-1] == "," or not alone:
        return []
    pieces = [piece.strip() for piece in LIST_RE.split(rest)]
    others = [authors.given_first(piece) for piece in pieces[:-1]]
    last = authors.parse_name(f"{family.strip()}, {pieces[-1]}")
    return [*others, last] if others and last and all(others) else []


def listed(part: str) -> list[Name]:
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
    again = leading_name("".join(pieces[len(run) :][:1]))
    twice = cut and again and (_same_family(cut, again) or same_given(cut, again))
    return [*run[:-1], cut if cut and twice else run[-1]]


def board_members(part: str) -> list[Name]:
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


def _same_family(name: Name, other: Name) -> bool:
    return spelling.fold(name.family) == spelling.fold(other.family)


def same_given(name: Name, earlier: Name) -> bool:
    """Tell whether two first given names are forms or misspellings of one name.

    One starts the other ('Tim', 'Timothy') or most of their letters agree ('Thmas',
    'Thomas'). 'Jane' and 'John' are two people of one family.
    """
    one, other = (spelling.fold(n.given.split()[0]) for n in (name, earlier))
    alike = difflib.SequenceMatcher(None, one, other).ratio() >= MIN_ALIKE
    return one.startswith(other) or other.startswith(one) or alike
