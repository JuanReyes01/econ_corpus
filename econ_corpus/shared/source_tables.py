"""Tables of where the parsed records come from, each a list of string rows, header first.

Used by step 3b (the datasheet of the raw table), next to the tables of `tables`.
Input: articles as a dict of columns, as in `tables`.
Output: tables for the datasheet and for the CSV files that sit next to it.

Lives here: the publications outside the queried newspapers, the online editions and their
blog label, and the download dates. Does not live here: the other counts of the datasheets
(tables), the template filling or any decision about which records to keep (exclusions).
"""

from collections import Counter, defaultdict

from econ_corpus.shared import summaries
from econ_corpus.shared.tables import BLOG_LABEL, TOP_N, Articles, Table


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
