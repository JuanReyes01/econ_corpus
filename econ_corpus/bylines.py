"""Used by steps 2, 4 and 5 of the pipeline: read the people named in a ProQuest byline.

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

import difflib
import itertools
import re

from econ_corpus import authors
from econ_corpus.authors import Name
from econ_corpus.name_words import HONORIFICS, SAINTS, SENTENCE_WORDS, SUFFIXES

JOINER_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)
LIST_RE = re.compile(r",|\s+(?:and|&)\s+", re.IGNORECASE)  # separators of a list of names
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
# The end of a note cut short because the export moved its last word to the front of the
# byline: 'Ann Roe is', 'Ann Roe is on', and the same turned round, 'Roe is, Ann'.
CUT_NOTE_RE = re.compile(r"\b(?:is|are)(?: on)?\.?$")
WRITER_NOTE_RE = re.compile(r"\bthe writers? (?:is|are)\b", re.IGNORECASE)  # of a letters page
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
LEAD_RE = re.compile(
    r"^(?:(?:and|&)\s+)?(?:by\s+)?", re.IGNORECASE
)  # 'And Jane Doe', 'By Jane Doe'
MIN_FAMILY = 4  # letters a family name needs to count as the start of a longer one
MIN_ALIKE = 0.8  # share of letters two given names must share to be one name misspelt
MIN_ALIKE_FAMILY = 0.85  # and two family names ('Doewoodsen', 'Doewodosen')
BIO_RE = re.compile(r"\b(?:is|was|are|were|has|had)\b")  # the verb of a sentence about someone
# The same verb with words after it; 'Do is, Jane' is a family name cut by a stray space.
GOES_ON_RE = re.compile(r"\b(?:is|was|are|were|has|had)\s+\w")
SENTENCE_END_RE = re.compile(r"\.['\"\u201d\u2019]*$")  # a period, and quotes closing after it
# 'and Andrew' comes out of the export as 'andrew': 'and' swallowed the start of the name.
AND_GLUED_RE = re.compile(r"(?<=\s)and(?=[a-z]+\s+[A-Z])")


def split_authors(raw: str | None) -> list[str]:
    """Split a byline into parts, one per author as written.

    ';' separates authors. A suffix standing alone ('Doe, John; Jr.') belongs to the name
    before it, and so does a given name cut off from its one-word family name ('Doe; , Jane').
    A part without a comma loses a leading 'By' and is split at 'and' or '&', unless what
    stands before the 'and' already holds a sentence about the first author ('Jane Doe is a
    teacher and ...') or the part is a note about people who did not write ('Jane Doe and Ann
    Roe are on vacation').
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
            sentence = BIO_RE.search(pieces[0]) if pieces else None
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


def _is_note(part: str) -> bool:
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


def _after_sentence(part: str) -> list[Name]:
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
    # 'Jane Doe and Richard Roe Jane Doe and ...': the list written again starts in the
    # last name of the run, which then ends in the first name of the list.
    first, last = (f"{name.given} {name.family}" for name in (run[0], run[-1]))
    again = last.endswith(f" {first}") and authors.given_first(last.removesuffix(first))
    return [name for name in [*run[:-1], again or run[-1]] if name]


def _board_members(part: str) -> list[Name]:
    """Read the names around the note of an editorial-board item.

    'Jane Doe. Richard Roe. Written by members of the editorial board.' lists the members
    who wrote it, one sentence each, before or after the note.
    """
    if not BOARD_RE.search(part):
        return []
    pieces = re.split(r"(?<=[a-z])\.+\s*", BOARD_RE.sub(".", part))
    names = [authors.given_first(piece.strip(". ")) for piece in pieces]
    return [name for name in names if name]


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
    part = SUFFIX_GLUED_RE.sub(r" \1", PERIOD_GLUED_RE.sub(" ", GLUED_RE.sub("", part)))
    part = LEAD_RE.sub("", part.strip())
    if _is_note(part):
        return [], ""
    name = authors.parse_name(part)
    if name:
        return [name], "as_written"
    names = recover_names(part)
    return names, "recovered" if names else ""


def _tokens(name: Name) -> list[str]:
    return sorted(filter(None, map(authors.fold, f"{name.given} {name.family}".split())))


def _same_given(name: Name, earlier: Name) -> bool:
    """Tell whether two first given names are forms or misspellings of one name.

    One starts the other ('Tim', 'Timothy') or most of their letters agree ('Thmas',
    'Thomas'). 'Jane' and 'John' are two people of one family.
    """
    one, other = (authors.fold(n.given.split()[0]) for n in (name, earlier))
    alike = difflib.SequenceMatcher(None, one, other).ratio() >= MIN_ALIKE
    return one.startswith(other) or other.startswith(one) or alike


def _repeats(name: Name, earlier: Name, part: str) -> str:
    """Say what a name recovered from a note is to a name read before it in the byline.

    '' if it is another person; 'drop' if it is the same person and the earlier reading
    stands; 'replace' if it is the same person, read better here. The note after a byline
    ('Jane Doe lives in ...') repeats the author, and a difference in spelling would make
    two authors of one.
    """
    if name.suffix and earlier.suffix and name.suffix != earlier.suffix:
        return ""  # a father and a son
    new, old = _tokens(name), _tokens(earlier)
    if new == old:
        # The same words: the earlier part had them the wrong way round ('Jane, Doe'), or
        # it is the same name, and then the earlier reading may hold a suffix.
        turned = authors.fold(name.given) != authors.fold(earlier.given)
        fuller = bool(name.suffix) and not earlier.suffix  # only the note gives the suffix
        return "replace" if turned or fuller else "drop"
    if set(new) < set(old):
        # The earlier part has a town where the family name goes ('Springfield, Jane Doe')
        # when its family name is no word of the note's name and the note is not cut at an
        # abbreviation, with the family name right after ('Jane McC.' of 'Jane McC. Roe').
        # Otherwise the note has a shorter form of the name ('Jane Doe' for 'Jane Q Doe').
        text = authors.fold(authors.BY_RE.sub("", part.strip()))
        cut = text.startswith(authors.fold(name.given + name.family + earlier.family))
        town = authors.fold(earlier.family) not in new
        return "replace" if town and not cut else "drop"
    close = authors.one_edit(authors.name_key(name), authors.name_key(earlier))
    # The note may also glue a word to the name ('Doeis'), cut it ('Doewo od') or use
    # another form of the given name ('Tim', 'Timothy'): the same family name, or one that
    # starts the other, after a given name that is alike.
    family, old_family = authors.fold(name.family), authors.fold(earlier.family)
    long_enough = min(len(family), len(old_family)) >= MIN_FAMILY
    starts = family.startswith(old_family) or old_family.startswith(family)
    near = difflib.SequenceMatcher(None, family, old_family).ratio() >= MIN_ALIKE_FAMILY
    alike = authors.one_edit(family, old_family) or (long_enough and (starts or near))
    again = set(old) < set(new) or close or (alike and _same_given(name, earlier))
    return "drop" if again else ""


def _piece_of_note(part: str, *, in_sentence: bool, moved: bool) -> bool:
    """Tell whether a part is a piece of a note that the export cut off, not an author."""
    turned_round = in_sentence and "," in part and bool(authors.parse_name(part))
    cut_short = moved and bool(CUT_NOTE_RE.search(part.partition(",")[0].strip()))
    return turned_round or cut_short


Found = dict[str, tuple[Name, str]]


def _with(found: Found, before: Found, name: Name, how: str, part: str) -> Found:
    """Return the names read so far with one more, unless it repeats one of them.

    `before` holds the names of the parts before this one: a name is compared with those,
    not with its neighbours in a list of names ('Mark Doe, Mary Doe and Ann Roe').
    """
    key = authors.name_key(name)
    if key in found:
        return found  # the same name again: the first reading stands
    for old_key, (old, _) in before.items():
        verdict = _repeats(name, old, part) if how == "recovered" and old_key in found else ""
        if verdict == "replace":  # the new reading takes the place of the earlier one
            return {
                (key if k == old_key else k): ((name, how) if k == old_key else v)
                for k, v in found.items()
            }
        if verdict == "drop":
            return found
    return found | {key: (name, how)}


def read_byline(
    raw: str | None, corrections: dict[str, str] | None = None
) -> list[tuple[Name, str]]:
    """Return the persons a byline names, in order, each once, with how each was read.

    A part listed in `corrections` (decisions of the manual review) is read from its corrected
    byline and marked 'manual_review'; the others are 'as_written' or 'recovered'. After a
    part that leaves a sentence about its author unfinished, a part written 'Family, Given' is
    a piece of that sentence which the export cut off and turned round ('Jane Doe was an aide
    to Presidents Poe and Richard Roe' gives 'Roe, Richard'), not an author. The editor's note
    of a letters page ('The writer is ...') is followed by the next letter writers, so it
    does not count.
    """
    found: Found = {}
    in_sentence = False
    parts = split_authors(raw)
    # 'vacation., Jane Doe; Ann Roe is on': the last word of the byline was moved to its
    # front, so a later part that ends in 'is' or 'is on' is the note it was cut from.
    moved = bool(parts) and bool(_after_sentence(parts[0]))
    for part in parts:
        if corrections and part in corrections:
            reviewed = (authors.reviewed_name(p) for p in corrections[part].split(";"))
            names = [name for name in reviewed if name]
            how = "manual_review"
        elif _piece_of_note(part, in_sentence=in_sentence, moved=moved):
            names, how = [], ""
        else:
            names, how = read_part(part)
        # What follows the last sentence that ended; the period of an initial ends none.
        unfinished = re.split(r"(?<=[a-z])\.\s+(?=[A-Z])", part)[-1]
        if SENTENCE_END_RE.search(part):
            in_sentence = False
        elif GOES_ON_RE.search(unfinished) and not (_is_note(part) or WRITER_NOTE_RE.search(part)):
            in_sentence = True
        before = dict(found)
        for name in names:
            found = _with(found, before, name, how, part)
    return list(found.values())


def people(raw: str | None, corrections: dict[str, str] | None = None) -> list[Name]:
    """Return the persons a byline names, in order, each once."""
    return [name for name, _ in read_byline(raw, corrections)]


def is_signed(raw: str | None) -> bool:
    """Tell whether a byline has anything other than ProQuest's 'Anonymous' marker."""
    return any(
        p.strip() and authors.lookup(p.strip()) != "anonymous" for p in (raw or "").split(";")
    )
