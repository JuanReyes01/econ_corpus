"""Used by step 4 of the pipeline: list the pairs of authors that look alike but are not merged.

Input: the names seen in the bylines (see `identity.Seen`) and the author each key belongs to.
Output: pairs of authors with the reason they look alike, to be reviewed by hand.

Lives here: the kinds of likeness: compatible names that never share a newspaper, groups with
a contradiction, keys one letter apart, short forms of a first name, and given and family
name swapped. Does not live here: the rule that merges names (identity) or the review.
"""

from collections import defaultdict
from itertools import combinations

from econ_corpus.names import identity
from econ_corpus.names.authors import Name, fold, one_edit
from econ_corpus.names.identity import Seen
from econ_corpus.names.name_words import NICKNAMES

MIN_KEY = 8  # shorter keys are too easily one letter apart by chance
MAX_NEIGHBOURS = 20  # ignore spellings shared by more keys than this
MIN_NICKNAME = 3  # letters a first name needs to count as the beginning of a longer one
Pair = tuple[str, str, str]


def _is_nickname(a: str, b: str) -> bool:
    """Tell whether one first name is a short form of the other ('Tim', 'Timothy')."""
    short, long = sorted((a, b), key=len)
    begins = len(short) >= MIN_NICKNAME and long.startswith(short)
    return a != b and (
        begins or long in NICKNAMES.get(short, ()) or short in NICKNAMES.get(long, ())
    )


def _is_initial(one: Name, other: Name) -> bool:
    """Tell whether the given names of one are only the initials of the other's.

    'J Doe' can be 'Jane Doe', and 'J Q Doe' can be 'Jane Q Doe' or 'Jane Quincy Doe'.
    'J Brad Doe' goes by Brad, so it is not listed with every first name that starts with J.
    """
    initials = [fold(word) for word in one.given.split()]
    words = [fold(word) for word in other.given.split() if fold(word)]
    lone = all(len(letter) == 1 for letter in initials) and bool(initials)
    stood_for = "".join(word[0] for word in words).startswith("".join(initials))
    return lone and stood_for and bool(words) and len(words[0]) > 1


def _near_pairs(seen: dict[str, Seen]) -> set[tuple[str, str]]:
    """Find keys one letter apart (added, dropped, changed or swapped) that share a newspaper."""
    spellings: defaultdict[str, set[str]] = defaultdict(set)
    for key in seen:
        if len(key) >= MIN_KEY:
            for i in range(len(key) + 1):
                spellings[key[:i] + key[i + 1 :]].add(key)  # i == len(key) keeps the key whole
    pairs = set()
    for keys in spellings.values():
        if 1 < len(keys) <= MAX_NEIGHBOURS:
            pairs |= {
                (a, b)
                for a, b in combinations(sorted(keys), 2)
                if seen[a].papers & seen[b].papers and one_edit(a, b)
            }
    return pairs


def _nickname_pairs(seen: dict[str, Seen]) -> set[tuple[str, str]]:
    """Find names that differ only by a short form or the initials of the given names.

    Unlike a letter of difference, a short form is listed across newspapers too: 'Chuck Doe'
    in one and 'Charles Doe' in another are worth a look.
    """
    by_family: defaultdict[str, list[str]] = defaultdict(list)
    for key in sorted(seen):
        by_family[fold(seen[key].name.family)].append(key)
    pairs = set()
    for keys in by_family.values():
        for a, b in combinations(keys, 2):
            one, other = seen[a], seen[b]
            short_form = (
                _is_nickname(identity.given(one.name)[0], identity.given(other.name)[0])
                or _is_initial(one.name, other.name)
                or _is_initial(other.name, one.name)
            )
            if short_form and identity.compatible(one.name, other.name):
                pairs.add((a, b))
    return pairs


def _swapped_pairs(seen: dict[str, Seen]) -> set[tuple[str, str]]:
    """Find names that also appear with given and family name swapped, in one newspaper."""
    pairs = set()
    for key, one in seen.items():
        swapped = fold(f"{one.name.family}{one.name.given}{one.name.suffix}")
        if swapped in seen and key < swapped and one.papers & seen[swapped].papers:
            pairs.add((key, swapped))
    return pairs


def candidates(seen: dict[str, Seen], resolved: dict[str, str]) -> list[Pair]:
    """List the pairs of authors that look alike but were not merged, with the reason.

    'no_shared_newspaper': compatible names that never appear in the same newspaper.
    'apart_by_review': compatible names that share a newspaper but were kept apart by a
    review. 'conflicting_names': names in a group with a contradiction. 'one_letter_apart':
    keys one letter apart that share a newspaper. 'nickname': given names that are a short
    form or the initials of each other, in any newspaper. 'swapped_names': the same two names
    with given and family name the other way round, in one newspaper.
    """
    found: dict[tuple[str, str], str] = {}
    for keys, consistent in identity.buckets(seen):
        papers: defaultdict[str, set[str]] = defaultdict(set)
        for key in keys:
            papers[resolved[key]] |= seen[key].papers
        for a, b in combinations(sorted(papers), 2):
            shared = "apart_by_review" if papers[a] & papers[b] else "no_shared_newspaper"
            found[a, b] = shared if consistent else "conflicting_names"
    others = (
        ("one_letter_apart", _near_pairs(seen)),
        ("nickname", _nickname_pairs(seen)),
        ("swapped_names", _swapped_pairs(seen)),
    )
    for kind, pairs in others:
        for a, b in pairs:
            pair = tuple(sorted((resolved[a], resolved[b])))
            if pair[0] != pair[1]:
                found.setdefault(pair, kind)
    return sorted((a, b, kind) for (a, b), kind in found.items())
