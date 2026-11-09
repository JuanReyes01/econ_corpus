"""Stage 7 of the pipeline: list the author cases that need a manual review.

Input: the cleaned tables written by `processed`, the records with their reasons, and the
parts already decided in a review.
Output, in `data/review/cases/`: `parts_to_review.csv` (byline parts whose reading is
ambiguous), `names_to_review.csv` (names that may be a place or a publication),
`rejected_to_review.csv` (parts read as nobody in articles left out for having no person
among their authors) and `pairs_to_review.csv` (look-alike authors not yet reviewed), each
with the evidence a reviewer needs.

Lives here: which cases are worth a review, and the evidence shown. Does not live here: the
decisions (taken by reading each case and kept in `data/review`, see `review`).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
import csv
from pathlib import Path
import sys

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus import authors, datasheet, reasons, review
from econ_corpus.bylines import is_signed, read_part, split_authors
from econ_corpus.name_words import WATCH_WORDS
from econ_corpus.tables import Table

MIN_ARTICLES = 2  # a pair is reviewed when both authors have at least this many articles
Article = tuple[str, int | None, str | None]  # newspaper, year, title


def _parts(bylines: Iterable[str | None], decided: set[str]) -> Iterator[str]:
    for byline in bylines:
        yield from (p for p in split_authors(byline) if p not in decided)


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
        words = [w for name in read_part(part)[0] for w in authors.display(name).split()]
        if any(authors.fold(piece) in WATCH_WORDS for w in words for piece in w.split("-")):
            found[part] += 1
    return found


def rejected_parts(bylines: Iterable[str | None], decided: set[str]) -> Counter:
    """Count the parts that name nobody, apart from ProQuest's 'Anonymous' marker.

    Most are institutions; some are a person's name that the rules could not read.
    """
    found: Counter = Counter()
    for part in _parts(bylines, decided):
        if is_signed(part) and not read_part(part)[0]:
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


def _dicts(table: Table) -> list[dict[str, str]]:
    """Return the rows of a table as dictionaries, so columns are looked up by name."""
    return [dict(zip(table[0], row, strict=True)) for row in table[1:]]


def _part_rows(parts: Counter, papers: dict[str, set[str]]) -> Table:
    rows = [
        [part, str(n), "/".join(sorted(papers[part])), _reading(part)]
        for part, n in sorted(parts.items())
    ]
    return [["part", "times", "newspapers", "read_now_as"], *rows]


def _reading(part: str) -> str:
    return "; ".join(authors.display(name) for name in read_part(part)[0])


def _pair_rows(clean: Path, article: dict[str, Article]) -> Table:
    """Return the pairs to review with, for each author, its key, name, articles and evidence."""
    docs: defaultdict[str, list[Article]] = defaultdict(list)
    for link in _dicts(_read(clean / "article_authors.csv")):
        docs[link["author_id"]].append(article[link["doc_id"]])
    names = _dicts(_read(clean / "author_names.csv"))
    key = {n["author_id"]: n["name_key"] for n in names if n["rule"] == "main"}
    candidates = _read(clean / "author_candidates.csv")
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


def build(records: Path, reasons_file: Path, clean: Path, review_dir: Path) -> dict[str, int]:
    """Write the cases to review into `review_dir/cases`; return how many of each."""
    columns = ["doc_id", "newspaper", "pub_year", "title", "author"]
    options = pacsv.ConvertOptions(include_columns=columns, column_types={"doc_id": pa.string()})
    parse = pacsv.ParseOptions(newlines_in_values=True)
    art = pacsv.read_csv(clean / "articles.csv", parse_options=parse, convert_options=options)
    art = art.to_pydict()
    decided = review.decided_parts(review_dir / review.PARTS_FILE)
    papers: defaultdict[str, set[str]] = defaultdict(set)
    for byline, paper in zip(art["author"], art["newspaper"], strict=True):
        for part in split_authors(byline):
            papers[part].add(paper)
    ambiguous = ambiguous_parts(art["author"], decided)
    watched = watched_parts(art["author"], decided | set(ambiguous))
    nobody = pc.equal(reasons.load(records, reasons_file), "no_person_author")
    unread = pq.read_table(records, columns=["author"]).filter(nobody)["author"].to_pylist()
    rejected = rejected_parts(unread, decided).most_common()
    article = dict(
        zip(
            art["doc_id"],
            zip(art["newspaper"], art["pub_year"], art["title"], strict=True),
            strict=True,
        )
    )
    tables = {
        "parts_to_review": _part_rows(ambiguous, papers),
        "names_to_review": _part_rows(watched, papers),
        "rejected_to_review": [["part", "times"], *([part, str(n)] for part, n in rejected)],
        "pairs_to_review": _pair_rows(clean, article),
    }
    for name, table in tables.items():
        datasheet.write_csv(table, review_dir / "cases" / f"{name}.csv")
    return {name: len(table) - 1 for name, table in tables.items()}


def main() -> None:
    """List the cases to review from the repo's default locations."""
    counts = build(
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        Path("data/processed/clean"),
        Path("data/review"),
    )
    print(", ".join(f"{name}: {n:,}" for name, n in counts.items()))  # noqa: T201


if __name__ == "__main__":
    main()
