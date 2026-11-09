"""Used by steps 2, 3b, 4 and 5 of the pipeline: read the people named in a ProQuest byline.

Input: the `author` value of a record, as exported (for example 'Doe, Jane Q; Roe, Richard').
Output: the persons it names, in order, each once, with how each was read.

Lives here: cutting a byline into parts, putting together the names of its parts (a name
repeated by the note after it counts once), and applying the corrections of the manual
review. Does not live here: reading one part (parts), deciding whether a text is a name
(authors) or the review files themselves (review).
"""

import difflib
import re

from econ_corpus.names import authors
from econ_corpus.names.authors import Name
from econ_corpus.names.name_words import SUFFIXES
from econ_corpus.names.parts import (
    JOINER_RE,
    SENTENCE_END_RE,
    after_sentence,
    is_note,
    read_part,
    same_given,
)

# The end of a note cut short because the export moved its last word to the front of the
# byline: 'Ann Roe is', 'Ann Roe is on', and the same turned round, 'Roe is, Ann'.
CUT_NOTE_RE = re.compile(r"\b(?:is|are)(?: on)?\.?$")
WRITER_NOTE_RE = re.compile(r"\bthe writers? (?:is|are)\b", re.IGNORECASE)  # of a letters page
MIN_FAMILY = 4  # letters a family name needs to count as the start of a longer one
MIN_ALIKE_FAMILY = 0.85  # and two family names ('Doewoodsen', 'Doewodosen')
BIO_RE = re.compile(r"\b(?:is|was|are|were|has|had)\b")  # the verb of a sentence about someone
# The same verb with words after it; 'Do is, Jane' is a family name cut by a stray space.
GOES_ON_RE = re.compile(r"\b(?:is|was|are|were|has|had)\s+\w")
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
            parts += [text] if sentence or is_note(text) else pieces
    return parts


def _tokens(name: Name) -> list[str]:
    return sorted(filter(None, map(authors.fold, f"{name.given} {name.family}".split())))


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
    again = set(old) < set(new) or close or (alike and same_given(name, earlier))
    return "drop" if again else ""


def _piece_of_note(part: str, *, in_sentence: bool, moved: bool) -> bool:
    """Tell whether a part is a piece of a note that the export cut off, not an author."""
    turned_round = in_sentence and "," in part and bool(authors.parse_name(part))
    cut_short = moved and bool(CUT_NOTE_RE.search(part.partition(",")[0].strip()))
    return turned_round or cut_short


Found = dict[str, tuple[Name, str]]
# Review mark of a part that is an author only as the first name of a byline (a producer).
CREDIT = "CREDIT"


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
    byline and marked 'manual_review'; the others are 'as_written' or 'recovered'. A part
    marked CREDIT is read by the rules when it gives the first name of the byline, and names
    nobody after another name: the producer of a podcast is listed after its host. After a
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
    moved = bool(parts) and bool(after_sentence(parts[0]))
    for part in parts:
        credit = bool(corrections) and corrections.get(part) == CREDIT
        if credit and found:
            names, how = [], ""
        elif corrections and part in corrections and not credit:
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
        elif GOES_ON_RE.search(unfinished) and not (is_note(part) or WRITER_NOTE_RE.search(part)):
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
