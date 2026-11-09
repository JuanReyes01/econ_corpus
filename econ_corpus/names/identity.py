"""Used by step 4 of the pipeline: decide which name keys are the same author.

Input: the names seen in the bylines, each with the newspapers it appears in and its
number of articles (see `authors` for the names and their keys).
Output: for every name key, the key of the author it belongs to.

Lives here: the rule that merges variants of a name, and how review verdicts bend it. Does
not live here: reading names (authors), listing the pairs that look alike but are not merged
(lookalikes), or reading the review files (review).

The rule: names with the same first name and family name are one author when their middle
names and suffixes do not contradict each other (one is missing, or one is the initial of
the other) and they are linked through shared newspapers (two variants can be joined by a
third that shares a newspaper with each). One contradiction among the names with
that first and family name ('Jane Q Doe' next to 'Jane R Doe') stops every merge among them,
because the plain 'Jane Doe' could then be either.
"""

from collections import defaultdict
from itertools import combinations
from typing import NamedTuple

from econ_corpus.names.authors import Name, fold


class Seen(NamedTuple):
    """A name as observed in the corpus."""

    name: Name
    papers: frozenset[str]
    articles: int


def given(name: Name) -> tuple[str, list[str]]:
    """Split the given names into the first name and the middle names, folded.

    Initials at the start are one first name however they are spaced ('E J' and 'EJ').
    """
    words = [w for w in map(fold, name.given.split()) if w]
    run = next((i for i, w in enumerate(words) if len(w) > 1), len(words))
    return ("".join(words[:run]), words[run:]) if run > 1 else (words[0], words[1:])


def _bucket(name: Name) -> tuple[str, str]:
    return given(name)[0], fold(name.family)


def _agree(a: str, b: str) -> bool:
    """Tell whether two middle names are the same, one being perhaps only an initial."""
    short, long = sorted((a, b), key=len)
    return a == b or (len(short) == 1 and long.startswith(short))


def compatible(a: Name, b: Name) -> bool:
    """Tell whether two names with the same first and family name can be one person.

    Middle names are compared one by one: a name missing on one side is fine, and so is an
    initial against the full name. A suffix on one side only is fine; two suffixes must match.
    """
    middles = all(_agree(x, y) for x, y in zip(given(a)[1], given(b)[1], strict=False))
    return middles and (not a.suffix or not b.suffix or a.suffix == b.suffix)


def buckets(seen: dict[str, Seen]) -> list[tuple[list[str], bool]]:
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


def resolve(
    seen: dict[str, Seen],
    same: list[tuple[str, str]] | None = None,
    apart: list[tuple[str, str]] | None = None,
) -> dict[str, str]:
    """Return, for every name key, the key of its author.

    `same` and `apart` come from a manual review. A group the rule would merge is left
    unmerged if it holds a pair judged `apart`, since the rule cannot tell which variants go
    with which of the two. Pairs judged `same` are merged after the rule, together with the
    variants each already has. An author is named by its variant with most articles; the
    longest name decides ties.
    """
    kept_apart = {frozenset(pair) for pair in apart or []}
    group_of: dict[str, list[str]] = {}
    for keys, consistent in buckets(seen):
        for group in _linked(keys, seen) if consistent else [[k] for k in keys]:
            if any(frozenset(pair) in kept_apart for pair in combinations(group, 2)):
                group_of |= {key: [key] for key in group}
            else:
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
