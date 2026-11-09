"""Step 4 of the pipeline: write the cleaned dataset as normalised tables.

Input: the parquet written by `parse` and the reasons written by `exclusions`.
Output, in one folder: `articles.csv` (the records whose reason is `kept`), `authors.csv`
(one row per author), `author_names.csv` (every name variant of each author and the rule that
linked it), `article_authors.csv` (the many-to-many link, with the position in the byline)
and `author_candidates.csv` (pairs of authors that look alike and were not merged), plus
`manifest.json`, the fingerprints of the inputs the tables were built from.

Lives here: building the tables and writing them. Does not live here: which records are kept
(exclusions), how a byline is read (authors), which names are one author (identity) or the
decisions of the manual review (review), which are applied here when their files exist.

Articles are keyed by ProQuest id. Author ids are numbered in the order of the name keys, so
the same input gives the same ids.
"""

from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus import (
    authors,
    datasheet,
    identity,
    lookalikes,
    manifest,
    reasons,
    review,
    summaries,
)
from econ_corpus.authors import Name
from econ_corpus.bylines import read_byline
from econ_corpus.tables import Table

BATCH_SIZE = 20_000  # rows per batch when streaming the articles
Corrections = dict[str, str]


def _commonest(spellings: Counter) -> Name:
    """Pick the spelling seen most often; one not written in capitals wins a tie."""
    return max(spellings, key=lambda n: (spellings[n], not f"{n.given}{n.family}".isupper(), n))


def _read_bylines(
    doc_ids: list[int], bylines: list[str | None], newspapers: list[str], corrections: Corrections
) -> tuple[dict[str, identity.Seen], list[tuple[int, dict[str, str]]]]:
    """Read every byline; return the names seen and, per article, its name keys in order."""
    spellings: defaultdict[str, Counter] = defaultdict(Counter)
    papers: defaultdict[str, set[str]] = defaultdict(set)
    per_article = []
    read: dict[str | None, list] = {}  # bylines repeat, so each distinct one is read once
    for doc_id, byline, paper in zip(doc_ids, bylines, newspapers, strict=True):
        if byline not in read:
            read[byline] = read_byline(byline, corrections)
        found = {authors.name_key(name): how for name, how in read[byline]}
        for name, _ in read[byline]:
            spellings[authors.name_key(name)][name] += 1
            papers[authors.name_key(name)].add(paper)
        per_article.append((doc_id, found))
    seen = {
        key: identity.Seen(_commonest(c), frozenset(papers[key]), sum(c.values()))
        for key, c in spellings.items()
    }
    return seen, per_article


def _author_cells(author_id: int, name: dict[int, str], articles: Counter) -> list[str]:
    return [str(author_id), name[author_id], str(articles[author_id])]


def _rule(key: str, resolved: dict[str, str], by_rule: dict[str, str]) -> str:
    """Say what linked a name key to its author: nothing, the rule or the manual review."""
    if resolved[key] == key:
        return "main"
    return "shared_newspaper" if by_rule[key] == by_rule[resolved[key]] else "manual_review"


def author_tables(
    doc_ids: list[int],
    bylines: list[str | None],
    newspapers: list[str],
    corrections: Corrections,
    decisions: review.Decisions,
) -> dict[str, Table]:
    """Build the author, name, link and candidate tables from the bylines of the articles.

    `corrections` and `decisions` come from the manual review: corrected byline parts, and
    pairs of name keys judged 'same', 'different' or 'unsure'.
    """
    seen, per_article = _read_bylines(doc_ids, bylines, newspapers, corrections)
    judged = {v: [pair for pair, d in decisions.items() if d == v] for v in ("same", "different")}
    by_rule = identity.resolve(seen, apart=judged["different"])
    resolved = identity.resolve(seen, same=judged["same"], apart=judged["different"])
    reviewed = review.verdicts(decisions, resolved)
    ids = {head: i for i, head in enumerate(sorted(set(resolved.values())), start=1)}
    links = [["doc_id", "author_id", "position", "read"]]
    articles: Counter = Counter()
    for doc_id, found in per_article:
        linked: dict[int, str] = {}  # an author named twice in a byline is linked once
        for key, how in found.items():
            linked.setdefault(ids[resolved[key]], how)
        for position, (author_id, how) in enumerate(linked.items(), start=1):
            links.append([str(doc_id), str(author_id), str(position), how])
            articles[author_id] += 1
    variants = Counter(resolved.values())
    name = {i: authors.display(seen[head].name) for head, i in ids.items()}
    people = [[str(i), name[i], str(articles[i]), str(variants[head])] for head, i in ids.items()]
    names = [
        [
            str(ids[resolved[key]]),
            authors.display(seen[key].name),
            key,
            str(seen[key].articles),
            _rule(key, resolved, by_rule),
        ]
        for key in sorted(seen, key=lambda k: (ids[resolved[k]], resolved[k] != k, k))
    ]
    doubts = [
        [
            *(cell for key in (a, b) for cell in _author_cells(ids[key], name, articles)),
            kind,
            reviewed.get((a, b), "not_reviewed"),
        ]
        for a, b, kind in lookalikes.candidates(seen, resolved)
    ]
    side = ["author_id", "name", "articles"]
    return {
        "authors": [[*side, "name_variants"], *people],
        "author_names": [["author_id", "name", "name_key", "articles", "rule"], *names],
        "article_authors": links,
        "author_candidates": [
            [f"{c}_a" for c in side] + [f"{c}_b" for c in side] + ["kind", "review"],
            *doubts,
        ],
    }


def _write_articles(records: Path, kept: pa.ChunkedArray, out: Path, batch_size: int) -> None:
    """Stream the kept rows into a CSV, adding the newspaper and its edition."""
    source = pq.ParquetFile(records)
    base = source.schema_arrow.remove(source.schema_arrow.get_field_index("is_footer"))
    schema = base.append(pa.field("newspaper", pa.string())).append(
        pa.field("edition", pa.string())
    )
    start = 0
    with pacsv.CSVWriter(out, schema) as writer:
        for batch in source.iter_batches(batch_size=batch_size):
            rows = batch.filter(kept.slice(start, batch.num_rows).combine_chunks())
            start += batch.num_rows
            keys = rows.column("publication_key").to_pylist()
            columns = [rows.column(name) for name in base.names]
            columns.append(pa.array([summaries.newspaper_family(k) for k in keys], pa.string()))
            columns.append(
                pa.array([summaries.edition(k) if k else None for k in keys], pa.string())
            )
            writer.write_batch(pa.record_batch(columns, schema=schema))


def build(
    records: Path,
    reasons_file: Path,
    out_dir: Path,
    batch_size: int = BATCH_SIZE,
    review_dir: Path | None = None,
) -> dict[str, int]:
    """Write the cleaned tables into `out_dir`; return the number of rows of each.

    The review files in `review_dir`, if any, must be the ones `exclusions` was run with:
    otherwise an article could be kept without a person among its authors, which is refused.
    """
    corrections = review.load_parts(review_dir / review.PARTS_FILE) if review_dir else {}
    decisions = review.load_pairs(review_dir / review.PAIRS_FILE) if review_dir else {}
    review.same_review(reasons_file, corrections)
    kept = pc.equal(reasons.load(records, reasons_file), "kept")
    rows = pq.read_table(records, columns=["doc_id", "author", "publication_key"]).filter(kept)
    newspapers = [summaries.newspaper_family(k) for k in rows["publication_key"].to_pylist()]
    doc_ids = rows["doc_id"].to_pylist()
    if None in doc_ids or len(set(doc_ids)) != len(doc_ids):
        msg = "every kept article needs its own ProQuest id, the key of the cleaned tables"
        raise ValueError(msg)
    tables = author_tables(doc_ids, rows["author"].to_pylist(), newspapers, corrections, decisions)
    unlinked = len(set(doc_ids)) - len({link[0] for link in tables["article_authors"][1:]})
    if unlinked:
        msg = f"{unlinked} kept articles name no person: run exclusions again with these reviews"
        raise ValueError(msg)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest.clear(out_dir)  # until the last table is written, the folder is not a dataset
    for name, table in tables.items():
        datasheet.write_csv(table, out_dir / f"{name}.csv")
    _write_articles(records, kept, out_dir / "articles.csv", batch_size)
    manifest.write(out_dir, records, reasons_file, review_dir)
    counts = {name: len(table) - 1 for name, table in tables.items() if name != "author_names"}
    return {"articles": rows.num_rows, **counts}


def main() -> None:
    """Build the cleaned dataset from the repo's default locations."""
    counts = build(
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        Path("data/processed/clean"),
        review_dir=review.folder(Path("data/review")),
    )
    print(", ".join(f"{name}: {n:,}" for name, n in counts.items()))  # noqa: T201


if __name__ == "__main__":
    main()
