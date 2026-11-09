"""Stage 4 of the pipeline: read the people named in a ProQuest byline.

Input: the `author` value of a record, as exported (for example 'Doe, Jane Q; Roe, Richard').
Output: the persons it names, each as a `Name` (given names, family name, suffix), with a
display form ('Jane Q Doe') and a key that is equal for spelling variants of one name.

Lives here: splitting a byline into parts, deciding whether a part is a person's name, and
the display form and key. Does not live here: deciding that two different keys are the same
person, or building the author tables.

A part is first read as written ('Family, Given' or 'Given Family'). If that fails, a full
name at its start is recovered ('Jane Doe. Springfield', 'Jane Doe is a columnist'); one word
is never taken as a name. A part with no full name (an institution, a sentence) names nobody.
"""

import re
from typing import NamedTuple
import unicodedata


class Name(NamedTuple):
    """A person's name as written, split into its pieces."""

    given: str
    family: str
    suffix: str


SUFFIXES = {"jr": "Jr", "sr": "Sr", "ii": "II", "iii": "III", "iv": "IV"}
HONORIFICS = {"dr", "prof", "professor", "rev", "sen", "rep", "gov", "mr", "mrs", "ms", "sir"}
HONORIFICS |= {"rabbi", "msgr"}
DEGREES = {"md", "phd", "esq", "jd", "dds", "rn", "mba", "dvm", "mph"}
# Lower-case words that belong to the family name ('Jane van Doe').
PARTICLES = {"von", "van", "vanden", "de", "del", "della", "der", "den", "di", "da", "la", "le"}
PARTICLES |= {"du", "dos", "das", "ter", "ten", "bin", "ibn", "al", "el"}
# Words that mark an institution or a sentence, never part of a name written given-name first.
ORG_WORDS = {
    "anonymous", "board", "staff", "editor", "editors", "editorial", "editorials", "reader",
    "readers", "contributor", "contributors", "opinion", "opinions", "news", "press", "times",
    "post", "tribune", "globe", "journal", "service", "services", "show", "podcast", "writer",
    "writers", "bureau", "wire", "report", "reports", "team", "desk", "today", "newsday",
    "associated", "reuters", "bloomberg", "university", "institute", "center", "committee",
    "council", "association", "foundation", "network", "republic", "sentinel", "herald",
    "gazette", "syndicate", "special", "essay", "compiled", "columnist", "column", "star",
    "the", "of", "is", "from", "for", "with", "was", "are", "who", "his", "her", "its",
    "former", "director", "president", "chairman", "senator", "representative", "governor",
    "executive", "member", "author", "letters", "county", "department", "college", "coalition",
    "alliance", "society", "statesman", "dispatch", "courier", "chronicle", "register",
    "observer", "examiner", "inquirer", "weekly", "magazine", "ledger", "media", "inc", "llc",
    "company", "group", "excerpted", "illustration", "photo", "cartoon", "debate", "usa",
    "guest",
}  # fmt: skip
# In 'Family, Given' form a family name can be an ORG_WORD ('Press, Jane'), so only these
# words rule a part out when they stand alone before the comma.
ROLE_WORDS = {"staff", "board", "editors", "editorial", "readers", "anonymous", "opinion"}
ROLE_WORDS |= {"contributor", "contributors"}

WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2019.\-][^\W\d_]+)*\.?")  # letters, with ' - . inside
INITIALS_RE = re.compile(r"(?:[^\W\d_]\.)+")  # 'J.' or 'J.Q.R.'
JOINER_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)
BY_RE = re.compile(r"^by\s+", re.IGNORECASE)
LIST_RE = re.compile(r",|\s+(?:and|&)\s+", re.IGNORECASE)  # separators of a list of names
NAME_END_RE = re.compile(r",|\s-\s|\d")  # what ends a name that other text follows
POSSESSIVES = ("'s", "\u2019s")
MAX_NATURAL, MAX_FAMILY, MAX_GIVEN = 5, 3, 4  # most words a name, or one side of it, may have


def _bare(token: str) -> str:
    """Return a word without periods and casefolded, for looking it up in the word lists."""
    return token.replace(".", "").casefold()


def split_authors(raw: str | None) -> list[str]:
    """Split a byline into parts, one per author as written.

    ';' separates authors. A suffix standing alone ('Doe, John; Jr.') belongs to the name
    before it. A part without a comma loses a leading 'By' and is split at 'and' or '&'.
    """
    parts: list[str] = []
    for piece in (raw or "").split(";"):
        text = piece.strip()
        if not text:
            continue
        if _bare(text) in SUFFIXES and parts:
            parts[-1] = f"{parts[-1]}, {SUFFIXES[_bare(text)]}"
        elif "," in text:
            parts.append(text)
        else:
            parts += [p.strip() for p in JOINER_RE.split(BY_RE.sub("", text)) if p.strip()]
    return parts


def _are_name_words(tokens: list[str]) -> bool:
    """Check that every word looks like part of a name.

    A final period is accepted only on initials, so a word that ends a sentence
    ('Doe. Springfield') is not.
    """
    return all(
        WORD_RE.fullmatch(t) and (not t.endswith(".") or INITIALS_RE.fullmatch(t)) for t in tokens
    )


def _drop_honorifics(tokens: list[str]) -> list[str]:
    while tokens and _bare(tokens[0]) in HONORIFICS:
        tokens = tokens[1:]
    return tokens


def _natural(text: str, suffix: str) -> Name | None:
    """Read 'Given Family', optionally with a suffix as the last word."""
    tokens = _drop_honorifics(text.split())
    if tokens and not suffix and _bare(tokens[-1]) in SUFFIXES:
        suffix, tokens = SUFFIXES[_bare(tokens[-1])], tokens[:-1]
    if not 2 <= len(tokens) <= MAX_NATURAL or not _are_name_words(tokens):  # noqa: PLR2004
        return None
    # Hyphenated words are checked piece by piece ('Times-Union').
    if any(piece in ORG_WORDS for t in tokens for piece in _bare(t).split("-")):
        return None
    if not all(t[0].isupper() for t in tokens if _bare(t) not in PARTICLES):
        return None
    # The family name is the last word plus the particles right before it.
    start = len(tokens) - 1
    while start > 1 and _bare(tokens[start - 1]) in PARTICLES:
        start -= 1
    return Name(" ".join(tokens[:start]), " ".join(tokens[start:]), suffix)


def _family_first(family: str, given: str, suffix: str) -> Name | None:
    """Read 'Family, Given', the form ProQuest writes for most authors."""
    family_words, given_words = family.split(), _drop_honorifics(given.split())
    if not 1 <= len(family_words) <= MAX_FAMILY or not 1 <= len(given_words) <= MAX_GIVEN:
        return None
    if not _are_name_words(family_words + given_words):
        return None
    if all(_bare(t) in DEGREES for t in given_words) or _bare(family) in ROLE_WORDS:
        return None
    if any(_bare(t) in ORG_WORDS for t in given_words):
        return None
    if not given_words[0][0].isupper() or not any(t[0].isupper() for t in family_words):
        return None
    return Name(" ".join(given_words), " ".join(family_words), suffix)


def parse_name(part: str) -> Name | None:
    """Return the person a part names, or None if it is not clearly a person's name."""
    sides = [side.strip() for side in part.split(",")]
    suffix = ""
    if len(sides) > 1 and _bare(sides[-1]) in SUFFIXES:
        suffix, sides = SUFFIXES[_bare(sides[-1])], sides[:-1]
    if len(sides) == 1:
        return _natural(sides[0], suffix)
    if len(sides) == 2:  # noqa: PLR2004
        return _family_first(sides[0], sides[1], suffix)
    return None


def _leading_name(part: str) -> Name | None:
    """Read a full name at the start of a part that goes on with other text.

    The name ends at a comma, a dash, a digit, a word that closes a sentence, a possessive
    or the first lower-case word. A name written twice in a row is read once.
    """
    words: list[str] = []
    for word in NAME_END_RE.split(BY_RE.sub("", part.strip()), maxsplit=1)[0].split():
        bare = _bare(word)
        if word[0].islower() and bare not in PARTICLES:
            break
        if word.endswith(POSSESSIVES):
            words.append(word[:-2])
            break
        ends_sentence = word.endswith(".") and not INITIALS_RE.fullmatch(word)
        if ends_sentence and bare not in HONORIFICS and bare not in SUFFIXES:
            words.append(word[:-1])
            break
        words.append(word)
    half = len(words) // 2
    if half and [w.casefold() for w in words[:half]] == [w.casefold() for w in words[half:]]:
        words = words[:half]
    return _natural(" ".join(words), "")


def recover_names(part: str) -> list[Name]:
    """Return the persons in a part that `parse_name` cannot read as written.

    Either the part is a list of names ('Jane Doe, Richard Roe and Ann Poe') or it starts
    with a full name followed by other text.
    """
    listed = [_natural(piece.strip(), "") for piece in LIST_RE.split(part)]
    if len(listed) > 1 and all(listed):
        return [name for name in listed if name]
    name = _leading_name(part)
    return [name] if name else []


def read_part(part: str) -> tuple[list[Name], str]:
    """Return the persons a part names and how they were read: 'as_written' or 'recovered'."""
    name = parse_name(part)
    if name:
        return [name], "as_written"
    names = recover_names(part)
    return names, "recovered" if names else ""


def display(name: Name) -> str:
    """Return the name given-name first; a name written in capitals gets normal casing."""
    words = f"{name.given} {name.family}".split()
    plain = [w for w in words if _bare(w) not in PARTICLES]
    if all(w.isupper() for w in plain):
        # Capitalise each run of letters, so O'DOE-ROE becomes O'Doe-Roe; initials stay.
        words = [
            w
            if "." in w or w not in plain
            else re.sub(r"[^\W\d_]+", lambda m: m[0].capitalize(), w)
            for w in words
        ]
    return " ".join([*words, name.suffix]).strip()


def name_key(name: Name) -> str:
    """Return a key equal for spelling variants of one name.

    Case, accents, periods, apostrophes, hyphens and spaces are ignored, so 'DOE, JANE Q.',
    'Jane Q Doe' and 'D oe, Jane Q' (a stray space from ProQuest) share a key. Middle names
    and suffixes are kept: deciding that 'John Doe' and 'John Doe Jr' are one person is
    not done here.
    """
    text = unicodedata.normalize("NFKD", f"{name.given}{name.family}{name.suffix}")
    return "".join(c for c in text.casefold() if c.isalnum())


def people(raw: str | None) -> list[Name]:
    """Return the persons a byline names, in order, each once."""
    seen: set[str] = set()
    names = []
    for part in split_authors(raw):
        for name in read_part(part)[0]:
            if name_key(name) not in seen:
                seen.add(name_key(name))
                names.append(name)
    return names


def is_signed(raw: str | None) -> bool:
    """Tell whether a byline has anything other than ProQuest's 'Anonymous' marker."""
    return any(p.strip() and _bare(p.strip()) != "anonymous" for p in (raw or "").split(";"))
