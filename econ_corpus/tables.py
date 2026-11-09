"""Descriptive tables of the parsed records, each a list of string rows, header first.

Input: articles as a dict of columns (rows of the parquet read with `to_pydict`): either the
shared table (no footers, no repeats) or the table as parsed (no footers).
Output: tables for the datasheet and for the CSV files that sit next to it.

Lives here: counts by newspaper, period, document type, section, language, missing
fields and download date. Does not live here: the prose, the template filling or any
decision about which records to keep (exclusions).
"""

from collections import Counter, defaultdict
from collections.abc import Callable

from econ_corpus import summaries

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
        counts["With author"] += author is not None
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
        signed[period] += author is not None
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


def doc_type_table(articles: Articles) -> Table:
    """Most common document-type labels; a multi-label value counts once per label."""
    records: Counter = Counter()
    signed: Counter = Counter()
    for value, author in zip(articles["doc_type"], articles["author"], strict=True):
        for label in summaries.split_labels(value):
            records[label] += 1
            signed[label] += author is not None
    body = [
        [k, summaries.num(n), summaries.pct(signed[k], n)] for k, n in records.most_common(TOP_N)
    ]
    return [["Document type", "Records", "With author"], *body]


def section_table(articles: Articles) -> Table:
    """Most common section labels, grouped ignoring case."""
    counts = Counter(s.strip().casefold() for s in articles["section"] if s)
    total = len(articles["section"])
    body = [[k, summaries.num(n), summaries.pct(n, total)] for k, n in counts.most_common(TOP_N)]
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


def other_publications_table(articles: Articles) -> Table:
    """Most common publications outside the queried newspapers, by their commonest label."""
    labels: defaultdict[str, Counter] = defaultdict(Counter)
    for key, name in zip(articles["publication_key"], articles["publication"], strict=True):
        if summaries.newspaper_family(key) == "Other":
            labels[key][name] += 1
    ranked = sorted(labels.items(), key=lambda kv: -sum(kv[1].values()))[:TOP_N]
    body = [[c.most_common(1)[0][0], summaries.num(sum(c.values()))] for _, c in ranked]
    return [["Publication", "Records"], *body]


def download_table(articles: Articles) -> Table:
    """Count records, blog/podcast/website records and publication years per download date."""
    records: Counter = Counter()
    blogs: Counter = Counter()
    years: defaultdict[str, list[int]] = defaultdict(list)
    rows = zip(
        articles["source_file"], articles["source_type_key"], articles["pub_year"], strict=True
    )
    for source_file, source, year in rows:
        day = summaries.download_date(source_file) or "unknown"
        records[day] += 1
        blogs[day] += source == BLOG_LABEL
        years[day] += [year] if year else []
    body = [
        [
            day,
            summaries.num(records[day]),
            summaries.num(blogs[day]),
            summaries.pct(blogs[day], records[day]),
            str(min(years[day])) if years[day] else "n/a",
            str(max(years[day])) if years[day] else "n/a",
        ]
        for day in sorted(records)
    ]
    header = [
        "Download date",
        "Records",
        "Blog/podcast/website",
        "Share",
        "First year",
        "Last year",
    ]
    return [header, *body]


def online_edition_table(articles: Articles) -> Table:
    """Show, per newspaper, its online records and whether the blog label ever varies by year.

    The label belongs to the publication edition, so each newspaper should be all or none.
    """
    seen: defaultdict[str, defaultdict[int | None, Counter]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    keys = articles["publication_key"]
    for key, source, year in zip(
        keys, articles["source_type_key"], articles["pub_year"], strict=True
    ):
        name = summaries.newspaper_family(key)
        if key and name != "Other" and summaries.edition(key) == "online":
            seen[name][year][source == BLOG_LABEL] += 1
    body = []
    for name in summaries.INTENDED_NEWSPAPERS.values():
        if name not in seen:
            continue
        by_year = seen[name]
        total = sum(sum(c.values()) for c in by_year.values())
        blog = sum(c[True] for c in by_year.values())
        known = [y for y in by_year if y]
        mixed = sum(1 for c in by_year.values() if c[True] and c[False])
        body.append(
            [
                name,
                summaries.num(total),
                str(min(known)) if known else "n/a",
                summaries.pct(blog, total),
                str(mixed),
            ]
        )
    return [
        [
            "Newspaper",
            "Online records",
            "First year",
            "Labelled blog/podcast/website",
            "Years with both labels",
        ],
        *body,
    ]


def blog_profile_table(articles: Articles) -> Table:
    """List the document types of the records labelled blog/podcast/website."""
    counts: Counter = Counter()
    total = 0
    for source, doc_type in zip(articles["source_type_key"], articles["doc_type"], strict=True):
        if source == BLOG_LABEL:
            total += 1
            counts.update(summaries.split_labels(doc_type))
    body = [
        [label, summaries.num(n), summaries.pct(n, total)] for label, n in counts.most_common(6)
    ]
    return [["Document type", "Blog-labelled records", "Share of blog-labelled"], *body]
