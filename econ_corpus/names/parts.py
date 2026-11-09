"""Used by steps 2, 3b, 4 and 5 of the pipeline: read the people named in one part of a byline.

Input: one part of a byline, as cut at ';' (for example 'Doe, Jane Q' or 'Jane Doe is a
columnist in Springfield').
Output: the persons it names and how they were read ('as_written' or 'recovered').

Lives here: cleaning the labels the export glued to a part, the notes about people who did
not write, the names after a sentence about them, and the order in which a part is tried.
Does not live here: deciding whether a text is a name (authors), the name at the start of a
part that goes on with other text (name_start), lists of names and board members
(name_lists), or cutting a byline into parts and putting their names together (bylines).

A part is first read as written. If that fails, a full name at its start is recovered
('Jane Doe. Springfield', 'Jane Doe is a columnist'); one word is never taken as a name. A
part with no full name (an institution, a sentence) names nobody, and so does a note that
someone did not write ('Jane Doe is on vacation').
"""

import re

from econ_corpus.names import authors, name_lists, name_start, name_tokens
from econ_corpus.names.authors import Name
from econ_corpus.names.name_words import SUFFIXES

JOINER_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)
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
# Work on a piece that is not writing it: 'contributed reporting', and the line that says who
# compiled it ('Compiled by Jane Doe', 'This page is compiled by ...', 'Jane Doe compiled
# this report'). 'compiled' further on in a part is a word of a sentence about its author.
CREDIT_RE = re.compile(
    r"\bcontributed (?:reporting|research)\b"
    r"|^\s*compiled\b|\b(?:is|was|are|were) compiled by\b|\bcompiled this\b",
    re.IGNORECASE,
)
# A period glued to the word after it ('Jane Q.Doe', "Jane Q.O'Doe", 'Jane Doe.These are'),
# but not the periods between initials ('J.Q.', 'M.D').
PERIOD_GLUED_RE = re.compile(r"(?<=[^\W\d_]\.)(?=[^\W\d_](?:[^\W\d_]|['\u2019]))")
SUFFIX_GLUED_RE = re.compile(r"(?<=[a-z])(Jr|Sr)\b")  # 'Jane DoeJr'
LEAD_RE = re.compile(
    r"^(?:(?:and|&)\s+)?(?:by\s+)?", re.IGNORECASE
)  # 'And Jane Doe', 'By Jane Doe'
SENTENCE_END_RE = re.compile(r"\.['\"\u201d\u2019]*$")  # a period, and quotes closing after it


def is_note(part: str) -> bool:
    """Tell whether a part says that the people it names did not write this article.

    'Jane Doe is on vacation.' is printed under another columnist's article; so are
    'Jane Doe and Ann Roe are on vacation.', a credit for reporting or research, and the
    line that says who compiled a piece (a page of quotes, of jokes, of letters).
    """
    *before, last = JOINER_RE.split(part)
    words, rest = name_start.leading(last)
    named = bool(words) and all(authors.given_first(piece.strip()) for piece in before)
    return bool(CREDIT_RE.search(part)) or (named and bool(ABSENT_RE.match(" ".join(rest))))


def after_sentence(part: str) -> list[Name]:
    """Read the names that follow the end of a sentence about them ('Committee., Jane Doe').

    The export moves the last word of the whole byline before its first name. That word ends
    a note about the authors, or a note about someone else that follows their names:
    'Jane Doe; Ann Roe is on vacation.' comes out as 'vacation., Jane Doe; Ann Roe is on', so
    the name after the moved word is always an author.
    """
    head, _, rest = part.partition(",")
    last = (
        name_tokens.lookup(SENTENCE_END_RE.sub("", head).split()[-1]) if head.strip(". ") else ""
    )
    closes = SENTENCE_END_RE.search(head) and not name_tokens.is_title(head.strip())
    if not closes or not last or last in SUFFIXES:
        return []
    names = [authors.given_first(piece.strip()) for piece in JOINER_RE.split(rest)]
    return [name for name in names if name] if all(names) else []


def recover_names(part: str) -> list[Name]:
    """Return the persons in a part that `authors.parse_name` cannot read as written.

    The part is a list of names ('Jane Doe, Richard Roe and Ann Poe'), or names after the
    end of a sentence about them, or co-authors scrambled by the export, or it starts with a
    full name followed by other text.
    """
    board = name_lists.board_members(part)
    if board:
        return board
    listed = name_lists.listed(part)
    if listed:
        return listed
    moved = after_sentence(part)
    if moved:
        return moved
    put_back = name_lists.unscrambled(part)
    if put_back:
        return put_back
    name = name_start.leading_name(part)
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
