"""Stage 7 of the pipeline: list the author cases that need a manual review.

Input: the cleaned tables written by `processed` and the parts already decided in a review.
Output, in `data/review/cases/`: `parts_to_review.csv` (byline parts whose reading is
ambiguous), `names_to_review.csv` (names that may be a place or a publication) and
`pairs_to_review.csv` (look-alike authors not yet reviewed), each with the evidence a
reviewer needs.

Lives here: which cases are worth a review, and the evidence shown. Does not live here: the
decisions (taken by reading each case and kept in `data/review`, see `review`).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
import csv
from pathlib import Path
import sys

import pyarrow as pa
import pyarrow.csv as pacsv

from econ_corpus import authors, datasheet, review
from econ_corpus.name_words import WATCH_WORDS
from econ_corpus.tables import Table

MIN_ARTICLES = 2  # a pair is reviewed when both authors have at least this many articles
Article = tuple[str, int | None, str | None]  # newspaper, year, title


def _parts(bylines: Iterable[str | None], decided: set[str]) -> Iterator[str]:
    for byline in bylines:
        yield from (p for p in authors.split_authors(byline) if p not in decided)


def ambiguous_parts(bylines: Iterable[str | None], decided: set[str]) -> Counter:
    """Count the parts read as 'Family, Given' whose family name has two or more words.

    Double surnames read this way are right; 'Jane Doe, Springfield' is not.
    """
    found: Counter = Counter()
    for part in _parts(bylines, decided):
        name = authors.parse_name(part) if "," in part else None
        if name and sum(not authors.is_particle(w) for w in name.family.split()) > 1:
            found[part] += 1
    return found


def watched_parts(bylines: Iterable[str | None], decided: set[str]) -> Counter:
    """Count the parts read as a person whose name holds a place or publication word."""
    found: Counter = Counter()
    for part in _parts(bylines, decided):
        words = [w for name in authors.read_part(part)[0] for w in authors.display(name).split()]
        if any(authors.fold(piece) in WATCH_WORDS for w in words for piece in w.split("-")):
            found[part] += 1
    return found


def pairs_to_review(candidates: Table, min_articles: int = MIN_ARTICLES) -> Table:
    """Return the candidate pairs not reviewed yet with enough articles on both sides."""
    head = candidates[0]
    a, b, status = head.index("articles_a"), head.index("articles_b"), head.index("review")
    return [
        row
        for row in candidates[1:]
        if row[status] == "not_reviewed" and min(int(row[a]), int(row[b])) >= min_articles
    ]


def evidence(articles: list[Article]) -> str:
    """Summarise an author's articles: newspapers with counts, years, and two titles."""
    papers = Counter(paper for paper, _, _ in articles).most_common(3)
    years = sorted(year for _, year, _ in articles if year)
    span = f"{years[0]}-{years[-1]}" if years else "?"
    titles = " // ".join((title or "")[:60] for _, _, title in articles[:2])
    return f"{'/'.join(f'{p}:{n}' for p, n in papers)} {span} | {titles}"


def _read(path: Path) -> Table:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def _part_rows(parts: Counter, papers: dict[str, set[str]]) -> Table:
    rows = [
        [part, str(n), "/".join(sorted(papers[part])), _reading(part)]
        for part, n in sorted(parts.items())
    ]
    return [["part", "times", "newspapers", "read_now_as"], *rows]


def _reading(part: str) -> str:
    return "; ".join(authors.display(name) for name in authors.read_part(part)[0])


def _side(cells: list[str], key: dict[str, str], docs: dict[str, list[Article]]) -> list[str]:
    """Return one author of a pair as key, name, articles and evidence."""
    author_id, name, articles = cells
    return [key[author_id], name, articles, evidence(docs[author_id])]


def build(clean: Path, review_dir: Path) -> dict[str, int]:
    """Write the cases to review into `review_dir/cases`; return how many of each."""
    columns = ["doc_id", "newspaper", "pub_year", "title", "author"]
    options = pacsv.ConvertOptions(include_columns=columns, column_types={"doc_id": pa.string()})
    parse = pacsv.ParseOptions(newlines_in_values=True)
    art = pacsv.read_csv(clean / "articles.csv", parse_options=parse, convert_options=options)
    art = art.to_pydict()
    decided = review.decided_parts(review_dir / review.PARTS_FILE)
    papers: defaultdict[str, set[str]] = defaultdict(set)
    for byline, paper in zip(art["author"], art["newspaper"], strict=True):
        for part in authors.split_authors(byline):
            papers[part].add(paper)
    ambiguous = ambiguous_parts(art["author"], decided)
    watched = watched_parts(art["author"], decided | set(ambiguous))
    article = dict(
        zip(
            art["doc_id"],
            zip(art["newspaper"], art["pub_year"], art["title"], strict=True),
            strict=True,
        )
    )
    by_author: defaultdict[str, list[Article]] = defaultdict(list)
    for doc_id, author_id, *_ in _read(clean / "article_authors.csv")[1:]:
        by_author[author_id].append(article[doc_id])
    key = {row[0]: row[2] for row in _read(clean / "author_names.csv")[1:] if row[4] == "main"}
    pairs = [
        [row[6], *_side(row[0:3], key, by_author), *_side(row[3:6], key, by_author)]
        for row in pairs_to_review(_read(clean / "author_candidates.csv"))
    ]
    side = ["key", "name", "articles", "evidence"]
    tables = {
        "parts_to_review": _part_rows(ambiguous, papers),
        "names_to_review": _part_rows(watched, papers),
        "pairs_to_review": [
            ["kind", *(f"{c}_a" for c in side), *(f"{c}_b" for c in side)],
            *pairs,
        ],
    }
    for name, table in tables.items():
        datasheet.write_csv(table, review_dir / "cases" / f"{name}.csv")
    return {name: len(table) - 1 for name, table in tables.items()}


def main() -> None:
    """List the cases to review from the repo's default locations."""
    counts = build(Path("data/processed/clean"), Path("data/review"))
    print(", ".join(f"{name}: {n:,}" for name, n in counts.items()))  # noqa: T201


if __name__ == "__main__":
    main()
