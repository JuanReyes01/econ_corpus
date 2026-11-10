"""Descriptive tables of the cleaned dataset, each a list of string rows, header first.

Input: columns of the cleaned tables written by `processed`, and the reasons of every row.
Output: tables for the datasheet of the cleaned dataset.

Lives here: the flow from the parsed rows to the cleaned dataset, and its part after the raw
table, and counts by newspaper, decade and other values. Does not live here: the prose, the
template filling or the figure (datasheet_clean, figures), or which records are kept
(exclusions).
"""

from collections import Counter
from collections.abc import Iterable
from typing import NamedTuple

from econ_corpus.raw.reasons import LEFT_OUT, REASONS
from econ_corpus.shared import summaries
from econ_corpus.shared.tables import Table

EDITIONS = ["print", "online", "pre-1997"]
Bin = tuple[str, int, int | None]  # label, lowest value, highest value (None for no limit)


class Step(NamedTuple):
    """One exclusion: what it removes, what remains and the table reached, if any."""

    code: str
    description: str
    removed: int
    remaining: int
    reached: str


def flow(reasons: Iterable[str]) -> list[Step]:
    """Return the exclusions in the order the datasets are built, with running totals.

    Reasons that leave the shared raw table come first, then the ones that only leave the
    cleaned dataset. Each row has one reason, so the order does not change the totals.
    """
    counts = Counter(reasons)
    remaining = sum(counts.values())
    dropped = [r for r in REASONS if r["dropped"]]
    ordered = [r for r in dropped if not r["in_raw"]] + [r for r in dropped if r["in_raw"]]
    last_raw = [r["code"] for r in ordered if not r["in_raw"]][-1]
    steps = []
    for reason in ordered:
        remaining -= counts[reason["code"]]
        reached = {last_raw: "Shared raw table", ordered[-1]["code"]: "Cleaned dataset"}
        steps.append(
            Step(
                reason["code"],
                reason["description"],
                counts[reason["code"]],
                remaining,
                reached.get(reason["code"], ""),
            )
        )
    return steps


def clean_steps(reasons: Iterable[str]) -> list[Step]:
    """Return the exclusions that leave the cleaned dataset only, from the raw table on.

    The raw table has its own datasheet, so the cleaned one starts where that table ends.
    """
    return [s for s in flow(reasons) if s.code not in LEFT_OUT]


def flow_table(steps: list[Step], *, start: str) -> Table:
    """Render the flow as a table whose first row names the total it starts from."""
    total = steps[0].remaining + steps[0].removed
    body = [
        [s.code, s.description, summaries.num(s.removed), summaries.num(s.remaining)]
        for s in steps
    ]
    header = ["Step", "Left out", "Records", "Remaining"]
    return [header, [start, "", "", summaries.num(total)], *body]


def counts_table(values: Iterable[str], first: str) -> Table:
    """Count each value, most common first, with its share."""
    counts = Counter(values)
    total = sum(counts.values())
    body = [[v, summaries.num(n), summaries.pct(n, total)] for v, n in counts.most_common()]
    return [[first, "Count", "Share"], *body]


def binned_table(numbers: Iterable[int], bins: list[Bin], first: str, counted: str) -> Table:
    """Count how many numbers fall in each named range."""
    values = list(numbers)
    body = []
    for label, low, high in bins:
        n = sum(low <= v and (high is None or v <= high) for v in values)
        body.append([label, summaries.num(n), summaries.pct(n, len(values))])
    return [[first, counted, "Share"], *body]


def newspaper_table(newspapers: list[str], editions: list[str]) -> Table:
    """Count articles per newspaper and edition, largest first, with a total row."""
    by_paper: dict[str, Counter] = {}
    for paper, edition in zip(newspapers, editions, strict=True):
        by_paper.setdefault(paper, Counter())[edition] += 1
    total = len(newspapers)

    def row(name: str, counts: Counter) -> list[str]:
        n = sum(counts.values())
        cells = [summaries.num(counts[e]) for e in EDITIONS]
        return [name, summaries.num(n), *cells, summaries.pct(n, total)]

    ranked = sorted(by_paper.items(), key=lambda kv: -sum(kv[1].values()))
    everything = sum(by_paper.values(), Counter())
    header = ["Newspaper", "Articles", "Print", "Online", "Pre-1997", "Share"]
    return [header, *(row(name, c) for name, c in ranked), row("Total", everything)]


def year_table(years: Iterable[int | None]) -> Table:
    """Count articles per publication year, in order, unknown years last."""
    counts = Counter(str(y) if y else "Unknown year" for y in years)
    ordered = sorted(counts, key=lambda y: (y == "Unknown year", y))
    return [["Year", "Articles"], *([y, summaries.num(counts[y])] for y in ordered)]


def decade_table(years: Iterable[int | None]) -> Table:
    """Count articles per decade of publication year."""
    counts = Counter(f"{y // 10 * 10}s" if y else "Unknown year" for y in years)
    total = sum(counts.values())
    body = [
        [d, summaries.num(counts[d]), summaries.pct(counts[d], total)]
        for d in sorted(counts, key=lambda d: (d == "Unknown year", d))
    ]
    return [["Decade", "Articles", "Share"], *body]
