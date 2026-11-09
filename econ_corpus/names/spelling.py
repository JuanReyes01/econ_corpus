"""Used by steps 2, 4 and 5 of the pipeline: write a name for display and compare spellings.

Input: a `Name` (see `authors`), or the text of a name.
Output: a display form ('Jane Q Doe'), a key that is equal for spelling variants of one
name, and whether two spellings are one letter apart.

Lives here: normal casing of words in capitals, the display form, the key and the folding
it relies on. Does not live here: reading a name from a byline (authors), or deciding that
two different keys are the same person (identity).
"""

import re
import unicodedata

from econ_corpus.names.authors import Name
from econ_corpus.names.name_tokens import MC_RE, in_capitals, is_particle
from econ_corpus.names.name_words import SUFFIXES

MIN_SHOUTED = 3  # letters a word in capitals needs to be a name, not initials ('JD')
VOWELS = set("aeiouy")


def _normal_case(word: str) -> str:
    """Give normal casing to a word in capitals: O'DOE-ROE is O'Doe-Roe, McDOE is McDoe."""
    mc = MC_RE.fullmatch(word)
    if mc:
        return mc[1] + _normal_case(mc[2])
    cased = re.sub(r"[^\W\d_]+", lambda m: m[0].capitalize(), word)
    cased = re.sub(r"^Mc([a-z])(?=[a-z]{2})", lambda m: "Mc" + m[1].upper(), cased)  # 'MCDOE'
    return re.sub("(['\u2019])S$", r"\1s", cased)  # a possessive keeps its small s


def display(name: Name) -> str:
    """Return the name given-name first, with normal casing for what was written in capitals.

    In a name all in capitals every word is fixed. In any other name only a word that is
    clearly not initials is: three or more capitals with a vowel ('JANE'), or capitals after
    a prefix ('DeDOE'). Other capitals stay ('JD Doe', 'JQD Doe').
    """
    words = f"{name.given} {name.family}".split()
    # Lower-case particles ('del') do not count when deciding that a name is in capitals.
    shouted = all(in_capitals(w) for w in words if not (w.islower() and is_particle(w)))

    def fix(word: str) -> bool:
        letters = [c for c in fold(word) if c.isalpha()]
        spoken = len(letters) >= MIN_SHOUTED and bool(VOWELS & set(letters))
        numeral = word in SUFFIXES.values()  # 'III' stays
        capitals = "." not in word and in_capitals(word) and not numeral
        return capitals and (shouted or spoken or not word.isupper())

    words = [_normal_case(w) if fix(w) else w for w in words]
    return " ".join([*words, name.suffix]).strip()


def fold(text: str) -> str:
    """Return the letters and digits of a text, casefolded and without accents."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text.casefold() if c.isalnum())


def one_edit(a: str, b: str) -> bool:
    """Tell whether one letter added, dropped or changed, or two neighbours swapped, gives b."""
    if len(a) > len(b):
        a, b = b, a
    i = next((k for k, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), len(a))
    if len(a) < len(b):
        return a[i:] == b[i + 1 :]
    swapped = a[i : i + 2] == b[i : i + 2][::-1] and a[i + 2 :] == b[i + 2 :]
    return a[i + 1 :] == b[i + 1 :] or swapped


def name_key(name: Name) -> str:
    """Return a key equal for spelling variants of one name.

    Case, accents, periods, apostrophes, hyphens and spaces are ignored, so 'DOE, JANE Q.',
    'Jane Q Doe' and 'D oe, Jane Q' (a stray space from ProQuest) share a key. Middle names
    and suffixes are kept: deciding that 'John Doe' and 'John Doe Jr' are one person is
    not done here.
    """
    return fold(f"{name.given}{name.family}{name.suffix}")
