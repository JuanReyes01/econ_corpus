"""Used by step 5 of the pipeline: list the cases about whole authors that need a review.

Input: the cleaned tables written by `processed` (author names, candidate pairs, links
between articles and authors) and the articles signed under each name key.
Output: tables of look-alike pairs not yet reviewed, authors merged from a name with a
suffix and one without, variants of one author years apart and judged pairs that apply to
nothing any more, each with the evidence a reviewer needs.

Lives here: which pairs and merges of authors are worth a review, and their evidence. Does
not live here: the cases about byline parts or writing the files (review_cases), or the
decisions (see `review`).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
import csv
from itertools import combinations
from pathlib import Path
import sys

from econ_corpus.names import spelling
from econ_corpus.names.bylines import read_byline
from econ_corpus.names.name_words import SUFFIXES
from econ_corpus.shared.tables import Table

MIN_ARTICLES = 2  # a pair is reviewed when both authors have at least this many articles
FREQUENT = 20  # or when one of them has at least this many
MIN_SUFFIX_MERGE = 3  # articles each form needs for a suffix merge to be listed
MIN_GAP = 5  # years from the last article of a variant to the first of another to list them
Article = tuple[str, int | None, str | None]  # newspaper, year, title


def suffix_merges(names: Table, decided: set[tuple[str, str]], min_articles: int) -> Table:
    """List the authors merged by the rule from a name with a suffix and one without.

    'John Doe' and 'John Doe Jr' are usually one person, but can be father and son; when both
    forms are frequent the merge is worth a look. Pairs already judged are left out.
    """
    by_author: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _dicts(names):
        by_author[row["author_id"]].append(row)
    cells = ("name_key", "name", "articles")
    rows = []
    for variants in by_author.values():
        suffixed = [v for v in variants if v["name"].split()[-1] in SUFFIXES.values()]
        plain = [v for v in variants if v not in suffixed]
        if not suffixed or not plain:
            continue
        pair = [max(group, key=lambda v: int(v["articles"])) for group in (plain, suffixed)]
        keys = tuple(sorted(v["name_key"] for v in pair))
        if keys not in decided and all(int(v["articles"]) >= min_articles for v in pair):
            rows.append([v[c] for v in pair for c in cells])
    header = ["key_a", "name_a", "articles_a", "key_b", "name_b", "articles_b"]
    return [header, *sorted(rows)]


def distant_merges(
    names: Table,
    signed: dict[str, list[Article]],
    decided: set[tuple[str, str]],
    min_gap: int = MIN_GAP,
) -> Table:
    """List the pairs of variants of one author that appear `min_gap` or more years apart.

    Two people with one name are merged when they wrote for the same newspaper in different
    decades (a father and a son, a writer of the 1990s and one of the 2020s); the years
    between the last article of one variant and the first of the other are the sign. `signed`
    holds the articles signed under each name key. Every pair of variants is compared,
    whatever joined them: a verdict of the review is on one pair, and says nothing of the
    other variants of the two authors it joins. Pairs already judged are left out, and so
    are variants with no dated article.
    """
    by_author: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _dicts(names):
        by_author[row["author_id"]].append(row)
    rows = []
    for variants in by_author.values():
        for a, b in combinations(sorted(variants, key=lambda v: v["name_key"]), 2):
            spans = [
                sorted(year for _, year, _ in signed.get(v["name_key"], []) if year)
                for v in (a, b)
            ]
            if not all(spans) or (a["name_key"], b["name_key"]) in decided:
                continue
            gap = max(spans[1][0] - spans[0][-1], spans[0][0] - spans[1][-1])
            if gap >= min_gap:
                cells = [
                    [v["name_key"], v["name"], v["articles"], evidence(signed[v["name_key"]])]
                    for v in (a, b)
                ]
                rows.append([*cells[0], *cells[1], str(gap)])
    cells = ("key", "name", "articles", "evidence")
    header = [f"{c}_{side}" for side in "ab" for c in cells]
    return [[*header, "years_apart"], *sorted(rows)]


def unused_pairs(decided: Iterable[tuple[str, str]], keys: set[str]) -> list[tuple[str, str]]:
    """List the judged pairs in which a name key belongs to no author any more."""
    return sorted(pair for pair in decided if not set(pair) <= keys)


def pairs_to_review(candidates: Table, min_articles: int = MIN_ARTICLES) -> Table:
    """Return the candidate pairs not reviewed yet that are worth a review.

    Both authors have enough articles, or one of them is a frequent author: a single article
    under a misspelt name ('Jane Deo') matters when it belongs to someone with hundreds.
    """
    head = candidates[0]
    a, b, status = head.index("articles_a"), head.index("articles_b"), head.index("review")

    def worth(row: list[str]) -> bool:
        counts = int(row[a]), int(row[b])
        return min(counts) >= min_articles or max(counts) >= FREQUENT

    return [row for row in candidates[1:] if row[status] == "not_reviewed" and worth(row)]


def evidence(articles: list[Article]) -> str:
    """Summarise an author's articles: newspapers with counts, years, and two titles."""
    papers = Counter(paper for paper, _, _ in articles).most_common(3)
    years = sorted(year for _, year, _ in articles if year)
    span = f"{years[0]}-{years[-1]}" if years else "?"
    titles = " // ".join((title or "")[:60] for _, _, title in articles[:2])
    return f"{'/'.join(f'{p}:{n}' for p, n in papers)} {span} | {titles}"


def read(path: Path) -> Table:
    """Read a CSV file of the cleaned tables, whose cells can be long texts."""
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def _dicts(table: Table) -> list[dict[str, str]]:
    """Return the rows of a table as dictionaries, so columns are looked up by name."""
    return [dict(zip(table[0], row, strict=True)) for row in table[1:]]


def by_variant(art: dict[str, list], corrections: dict[str, str]) -> dict[str, list[Article]]:
    """Return the articles signed under each name key, reading the bylines as `processed` does."""
    read: dict[str | None, set[str]] = {}  # bylines repeat, so each distinct one is read once
    signed: defaultdict[str, list[Article]] = defaultdict(list)
    cells = zip(art["author"], art["newspaper"], art["pub_year"], art["title"], strict=True)
    for byline, *article in cells:
        if byline not in read:
            names = read_byline(byline, corrections)
            read[byline] = {spelling.name_key(name) for name, _ in names}
        for key in read[byline]:
            signed[key].append(tuple(article))
    return signed


def pair_rows(clean: Path, article: dict[str, Article]) -> Table:
    """Return the pairs to review with, for each author, its key, name, articles and evidence."""
    docs: defaultdict[str, list[Article]] = defaultdict(list)
    for link in _dicts(read(clean / "article_authors.csv")):
        docs[link["author_id"]].append(article[link["doc_id"]])
    names = _dicts(read(clean / "author_names.csv"))
    key = {n["author_id"]: n["name_key"] for n in names if n["rule"] == "main"}
    candidates = read(clean / "author_candidates.csv")
    cells = ["key", "name", "articles", "evidence"]
    rows = []
    for pair in _dicts([candidates[0], *pairs_to_review(candidates)]):
        row = [pair["kind"]]
        for side in "ab":
            author = pair[f"author_id_{side}"]
            row += [key[author], pair[f"name_{side}"], pair[f"articles_{side}"]]
            row.append(evidence(docs[author]))
        rows.append(row)
    return [["kind", *(f"{c}_a" for c in cells), *(f"{c}_b" for c in cells)], *rows]
