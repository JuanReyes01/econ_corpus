"""Stage 5 of the pipeline: decide which name keys are the same author.

Input: the names seen in the bylines, each with the newspapers it appears in and its
number of articles (see `authors` for the names and their keys).
Output: for every name key, the key of the author it belongs to, and the pairs of authors
that look alike but are not merged, to be reviewed by hand.

Lives here: the rule that merges variants of a name, and the list of doubtful pairs. Does
not live here: reading names (authors), or applying decisions taken in a manual review.

The rule: names with the same first name and family name are one author when their middle
names and suffixes do not contradict each other (one is missing, or one is the initial of
the other) and they share at least one newspaper. One contradiction among the names with
that first and family name ('Jane Q Doe' next to 'Jane R Doe') stops every merge among them,
because the plain 'Jane Doe' could then be either.
"""

from collections import defaultdict
from itertools import combinations
from typing import NamedTuple

from econ_corpus.authors import Name, fold

MIN_KEY = 9  # shorter keys are too easily one letter apart by chance
MAX_NEIGHBOURS = 20  # ignore spellings shared by more keys than this


class Seen(NamedTuple):
    """A name as observed in the corpus."""

    name: Name
    papers: frozenset[str]
    articles: int


Pair = tuple[str, str, str]


def _bucket(name: Name) -> tuple[str, str]:
    return fold(name.given.split()[0]), fold(name.family)


def _middle(name: Name) -> str:
    return fold(" ".join(name.given.split()[1:]))


def compatible(a: Name, b: Name) -> bool:
    """Tell whether two names with the same first and family name can be one person."""
    mid_a, mid_b = _middle(a), _middle(b)
    middles = not mid_a or not mid_b or mid_a.startswith(mid_b) or mid_b.startswith(mid_a)
    return middles and (not a.suffix or not b.suffix or a.suffix == b.suffix)


def _buckets(seen: dict[str, Seen]) -> list[tuple[list[str], bool]]:
    """Group the keys by first and family name, and say whether each group is consistent."""
    groups: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for key in sorted(seen):
        groups[_bucket(seen[key].name)].append(key)
    return [
        (keys, all(compatible(seen[a].name, seen[b].name) for a, b in combinations(keys, 2)))
        for keys in groups.values()
    ]


def _linked(keys: list[str], seen: dict[str, Seen]) -> list[list[str]]:
    """Split keys into groups connected through shared newspapers."""
    groups: list[list[str]] = []
    for key in keys:
        joined = [g for g in groups if any(seen[key].papers & seen[k].papers for k in g)]
        merged = [key, *(k for g in joined for k in g)]
        groups = [g for g in groups if g not in joined] + [merged]
    return groups


def resolve(seen: dict[str, Seen], same: list[tuple[str, str]] | None = None) -> dict[str, str]:
    """Return, for every name key, the key of its author.

    `same` lists pairs of keys that a manual review found to be one person; they are merged
    after the rule, together with the variants each already has. An author is named by its
    variant with most articles; the longest name decides ties.
    """
    group_of: dict[str, list[str]] = {}
    for keys, consistent in _buckets(seen):
        for group in _linked(keys, seen) if consistent else [[k] for k in keys]:
            group_of |= dict.fromkeys(group, group)
    for a, b in same or []:
        if a in group_of and b in group_of and group_of[a] is not group_of[b]:
            merged = group_of[a] + group_of[b]
            group_of |= dict.fromkeys(merged, merged)
    resolved = {}
    for key, group in group_of.items():
        if key not in resolved:
            head = max(group, key=lambda k: (seen[k].articles, len(k), k))
            resolved |= dict.fromkeys(group, head)
    return resolved


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
                (a, b) for a, b in combinations(sorted(keys), 2) if seen[a].papers & seen[b].papers
            }
    return pairs


def candidates(seen: dict[str, Seen], resolved: dict[str, str]) -> list[Pair]:
    """List the pairs of authors that look alike but were not merged, with the reason.

    'no_shared_newspaper': compatible names that never appear in the same newspaper.
    'conflicting_names': names in a group with a contradiction. 'one_letter_apart': keys
    one letter apart that share a newspaper.
    """
    found: dict[tuple[str, str], str] = {}
    for keys, consistent in _buckets(seen):
        kind = "no_shared_newspaper" if consistent else "conflicting_names"
        heads = sorted({resolved[k] for k in keys})
        found |= dict.fromkeys(combinations(heads, 2), kind)
    for a, b in _near_pairs(seen):
        pair = tuple(sorted((resolved[a], resolved[b])))
        if pair[0] != pair[1]:
            found.setdefault(pair, "one_letter_apart")
    return sorted((a, b, kind) for (a, b), kind in found.items())
