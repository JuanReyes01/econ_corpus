"""Step 5 of the pipeline: list the author cases that need a manual review.

Input: the cleaned tables written by `processed`, the records with their reasons, and the
parts already decided in a review.
Output, in `data/review/cases/`: `parts_to_review.csv` (byline parts whose reading is
ambiguous), `names_to_review.csv` (names that may be a place or a publication, long names
and names read by moving pieces around),
`rejected_to_review.csv` (parts read as nobody, in kept articles and in those left out for
having no person among their authors), `pairs_to_review.csv` (look-alike authors not yet
reviewed), `merged_to_review.csv` (authors merged from a name with a suffix and one
without) and `distant_to_review.csv` (variants of one author that appear years apart),
each with the evidence a reviewer needs; and `unused_parts.csv` and
`unused_pairs.csv`, the decisions that apply to nothing any more, to be retired.

Lives here: which cases are worth a review, and the evidence shown. Does not live here: the
decisions (taken by reading each case and kept in `data/review`, see `review`).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
import csv
from itertools import combinations
from pathlib import Path
import re
import sys

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus import authors, datasheet, manifest, reasons, review
from econ_corpus.bylines import is_signed, read_byline, read_part, split_authors, unscrambled
from econ_corpus.name_words import SUFFIXES, WATCH_WORDS
from econ_corpus.tables import Table

GLUED_BY_RE = re.compile(r"(?i:by)[^\W\d_]{4,}")  # a first name such as 'BYJANE'
MIN_ARTICLES = 2  # a pair is reviewed when both authors have at least this many articles
FREQUENT = 20  # or when one of them has at least this many
LONG_NAME = 4  # words in a name from which it is worth a second look
MIN_SUFFIX_MERGE = 3  # articles each form needs for a suffix merge to be listed
MIN_GAP = 5  # years from the last article of a variant to the first of another to list them
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
    """Count the parts read as a person whose name deserves a second look.

    The name holds a place or publication word; or it has four or more words, which is
    often two people or a name with something attached; or it was read by moving pieces
    around: a title where the family name goes ('Sen, Jane Doe'), which can be the family
    name Sen, or co-authors put back in order ('Doe, Jane Roe and Ann'); or the export may
    have damaged it: a lone small letter ('Doe, Jane e' is Jane E. or Janee) or 'BY' glued to
    the first name ('DOE, BYJANE').
    """
    found: Counter = Counter()
    for part in _parts(bylines, decided):
        names = read_part(part)[0]
        words = [w for name in names for w in authors.display(name).split()]
        long = any(len(f"{n.given} {n.family}".split()) >= LONG_NAME for n in names)
        moved = authors.is_title(part.partition(",")[0].strip()) or names == unscrambled(part)
        watched = any(authors.fold(p) in WATCH_WORDS for w in words for p in w.split("-"))
        damaged = any(len(w) == 1 and w.islower() for w in words) or any(
            GLUED_BY_RE.fullmatch(n.given.split()[0]) for n in names
        )
        if names and (long or watched or moved or damaged):
            found[part] += 1
    return found


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


def rejected_parts(bylines: Iterable[str | None], decided: set[str]) -> Counter:
    """Count the parts that name nobody, apart from ProQuest's 'Anonymous' marker.

    Most are institutions; some are a person's name that the rules could not read.
    """
    found: Counter = Counter()
    for part in _parts(bylines, decided):
        if is_signed(part) and not read_part(part)[0]:
            found[part] += 1
    return found


def unused_parts(bylines: Iterable[str | None], decided: set[str]) -> list[str]:
    """List the decided parts that no byline holds any more.

    A change in how bylines are split leaves decisions that apply to nothing; they would
    still be counted as reviewed cases, so they are listed to be retired.
    """
    held = {part for byline in bylines for part in split_authors(byline)}
    return sorted(decided - held)


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


def _by_variant(art: dict[str, list], corrections: dict[str, str]) -> dict[str, list[Article]]:
    """Return the articles signed under each name key, reading the bylines as `processed` does."""
    read: dict[str | None, set[str]] = {}  # bylines repeat, so each distinct one is read once
    signed: defaultdict[str, list[Article]] = defaultdict(list)
    cells = zip(art["author"], art["newspaper"], art["pub_year"], art["title"], strict=True)
    for byline, *article in cells:
        if byline not in read:
            names = read_byline(byline, corrections)
            read[byline] = {authors.name_key(name) for name, _ in names}
        for key in read[byline]:
            signed[key].append(tuple(article))
    return signed


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
    """Write the cases to review into `review_dir/cases`; return how many of each.

    The cleaned tables must have been built from these reasons and review files: cases listed
    from older tables would repeat decided ones or miss new ones.
    """
    manifest.check(clean, records, reasons_file, review_dir)
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
    every_byline = pq.read_table(records, columns=["author"])["author"]
    unread = every_byline.filter(nobody).to_pylist()
    names = _read(clean / "author_names.csv")
    keys = {row[names[0].index("name_key")] for row in names[1:]}
    judged = review.load_pairs(review_dir / review.PAIRS_FILE)
    signed = _by_variant(art, review.load_parts(review_dir / review.PARTS_FILE))
    # A kept article can also hold a part that names nobody, next to one that names a person.
    rejected = rejected_parts([*unread, *art["author"]], decided).most_common()
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
        "merged_to_review": suffix_merges(names, set(judged), MIN_SUFFIX_MERGE),
        "distant_to_review": distant_merges(names, signed, set(judged)),
        "unused_parts": [
            ["part"],
            *([part] for part in unused_parts(every_byline.unique().to_pylist(), decided)),
        ],
        "unused_pairs": [["key_a", "key_b"], *map(list, unused_pairs(judged, keys))],
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
        review.folder(Path("data/review")),
    )
    print(", ".join(f"{name}: {n:,}" for name, n in counts.items()))  # noqa: T201


if __name__ == "__main__":
    main()
