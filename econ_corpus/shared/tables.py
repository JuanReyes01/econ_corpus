"""Descriptive tables of the parsed records, each a list of string rows, header first.

Input: articles as a dict of columns (rows of the parquet read with `to_pydict`): either the
shared table (no footers, no repeats) or the table as parsed (no footers).
Output: tables for the datasheet and for the CSV files that sit next to it.

Lives here: counts by newspaper, period, document type, section, language and missing
fields, and writing a table. Does not live here: the tables of where the records come from
(source_tables), the prose, the template filling or any decision about which records to keep
(exclusions).
"""

from collections import Counter, defaultdict
from collections.abc import Callable
import csv
from pathlib import Path

from econ_corpus.names import bylines
from econ_corpus.shared import summaries

Articles = dict[str, list]
Table = list[list[str]]
TOP_N = 12  # rows shown in "top labels" tables
BLOG_LABEL = "blog,podcastositioweb"  # source_type_key of blogs, podcasts and websites


def md_table(rows: Table) -> str:
    """Render rows (header first) as a markdown table."""
    header, *body = rows
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)


def newspaper_table(articles: Articles) -> Table:
    """Count records per newspaper by edition, source type and share with a named author."""
    stats: defaultdict[str, Counter] = defaultdict(Counter)
    rows = zip(
        articles["publication_key"], articles["source_type_key"], articles["author"], strict=True
    )
    for key, source, author in rows:
        counts = stats[summaries.newspaper_family(key) or "No metadata"]
        counts["Records"] += 1
        counts[summaries.edition(key) if key else "none"] += 1
        counts["Blog/podcast/website"] += source == BLOG_LABEL
        counts["With author"] += bylines.is_signed(author)
    header = ["Newspaper", "Records", "Print", "Online", "Pre-1997", "Blog/podcast/website"]
    names = [*summaries.INTENDED_NEWSPAPERS.values(), "Other", "No metadata"]
    total = Counter(sum(stats.values(), Counter()))

    def row(name: str, c: Counter) -> list[str]:
        cells = [c["Records"], c["print"], c["online"], c["pre-1997"], c["Blog/podcast/website"]]
        return [name, *map(summaries.num, cells), summaries.pct(c["With author"], c["Records"])]

    body = [row(name, stats[name]) for name in names]
    return [[*header, "With author"], *body, row("Total", total)]


def _period_table(articles: Articles, label: Callable[[int | None], str], first: str) -> Table:
    """Count records, unique ids and signed records per period of `pub_year`."""
    records: Counter = Counter()
    signed: Counter = Counter()
    ids: defaultdict[str, set] = defaultdict(set)
    for year, doc_id, author in zip(
        articles["pub_year"], articles["doc_id"], articles["author"], strict=True
    ):
        period = label(year)
        records[period] += 1
        signed[period] += bylines.is_signed(author)
        if doc_id is not None:
            ids[period].add(doc_id)
    body = [
        [
            p,
            summaries.num(records[p]),
            summaries.num(len(ids[p])),
            summaries.pct(signed[p], records[p]),
        ]
        for p in sorted(records, key=lambda x: (x == "Unknown year", x))
    ]
    return [[first, "Records", "Unique ids", "With author"], *body]


def year_comparison_table(parsed: Articles, shared: Articles) -> Table:
    """Count records per publication year as parsed and in the shared table."""
    before = Counter(y for y in parsed["pub_year"] if y)
    after = Counter(y for y in shared["pub_year"] if y)
    body = [[str(y), summaries.num(before[y]), summaries.num(after[y])] for y in sorted(before)]
    return [["Year", "As parsed", "Shared table"], *body]


def decade_table(articles: Articles) -> Table:
    """Count records per decade of publication year.

    Meant for the shared table, where ids do not repeat, so the id column is left out.
    """
    rows = _period_table(articles, lambda y: f"{y // 10 * 10}s" if y else "Unknown year", "Decade")
    return [[decade, records, signed] for decade, records, _, signed in rows]


def year_table(articles: Articles) -> Table:
    """Count records per publication year."""
    return _period_table(articles, lambda y: str(y) if y else "Unknown year", "Year")


class _Labels:
    """Counts of labels grouped despite case and stray spaces ('News', 'New s', 'NEWS')."""

    def __init__(self) -> None:
        self.counts: Counter = Counter()
        self._spellings: defaultdict[str, Counter] = defaultdict(Counter)

    def add(self, label: str) -> str:
        """Count a label; return the key of its group."""
        key = summaries.label_key(label)
        self.counts[key] += 1
        self._spellings[key][label.strip()] += 1
        return key

    def top(self, rows: int = TOP_N) -> list[tuple[str, str, int]]:
        """Return key, commonest spelling and count of the most common groups."""
        return [
            (key, self._spellings[key].most_common(1)[0][0], n)
            for key, n in self.counts.most_common(rows)
        ]


def doc_type_table(articles: Articles) -> Table:
    """Most common document-type labels; a multi-label value counts once per label."""
    labels = _Labels()
    signed: Counter = Counter()
    for value, author in zip(articles["doc_type"], articles["author"], strict=True):
        for label in summaries.split_labels(value):
            signed[labels.add(label)] += bylines.is_signed(author)
    body = [[name, summaries.num(n), summaries.pct(signed[k], n)] for k, name, n in labels.top()]
    return [["Document type", "Records", "With author"], *body]


def section_table(articles: Articles) -> Table:
    """Most common section labels, grouped despite case and stray spaces."""
    labels = _Labels()
    for section in articles["section"]:
        if section:
            labels.add(section)
    total = len(articles["section"])
    body = [[name, summaries.num(n), summaries.pct(n, total)] for _, name, n in labels.top()]
    return [["Section", "Records", "Share"], *body]


def language_table(articles: Articles) -> Table:
    """Group the language field into English only, includes Spanish, other and missing."""

    def group(key: str | None) -> str:
        if key is None:
            return "Missing"
        if key == "english":
            return "English only"
        return "Includes Spanish" if "spanish" in key else "Other"

    counts = Counter(group(k) for k in articles["language_key"])
    total = len(articles["language_key"])
    body = [[k, summaries.num(n), summaries.pct(n, total)] for k, n in counts.most_common()]
    return [["Language", "Records", "Share"], *body]


def missing_table(articles: Articles) -> Table:
    """Count records missing each key field (a date that is not fully parsed counts)."""
    total = len(articles["title"])
    checks = {
        "Title": [v is None for v in articles["title"]],
        "Author": [v is None for v in articles["author"]],
        "Section": [v is None for v in articles["section"]],
        "Full publication date": [v != "ok" for v in articles["date_status"]],
        "Document id": [v != "ok" for v in articles["id_status"]],
        "Body text": [not v for v in articles["has_body"]],
    }
    body = [[k, summaries.num(sum(v)), summaries.pct(sum(v), total)] for k, v in checks.items()]
    return [["Field", "Missing", "Share"], *body]


def blog_profile_table(articles: Articles) -> Table:
    """List the document types of the records labelled blog/podcast/website."""
    labels = _Labels()
    total = 0
    for source, doc_type in zip(articles["source_type_key"], articles["doc_type"], strict=True):
        if source == BLOG_LABEL:
            total += 1
            for label in summaries.split_labels(doc_type):
                labels.add(label)
    body = [[name, summaries.num(n), summaries.pct(n, total)] for _, name, n in labels.top(6)]
    return [["Document type", "Blog-labelled records", "Share of blog-labelled"], *body]


def write_csv(rows: Table, path: Path) -> None:
    """Write a table to a CSV file, creating the folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
