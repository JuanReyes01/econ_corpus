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

Lives here: which byline parts are worth a review, the evidence shown for them, and writing
every file of cases. Does not live here: the cases about pairs and merges of authors
(author_cases), or the decisions (taken by reading each case and kept in `data/review`, see
`review`).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus.clean import author_cases, manifest
from econ_corpus.names import authors, name_tokens, review, spelling
from econ_corpus.names.bylines import is_signed, split_authors
from econ_corpus.names.name_lists import unscrambled
from econ_corpus.names.name_words import WATCH_WORDS
from econ_corpus.names.parts import read_part
from econ_corpus.raw import reasons
from econ_corpus.shared.tables import Table, write_csv

GLUED_BY_RE = re.compile(r"(?i:by)[^\W\d_]{4,}")  # a first name such as 'BYJANE'
LONG_NAME = 4  # words in a name from which it is worth a second look


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
        if name and sum(not name_tokens.is_particle(w) for w in name.family.split()) > 1:
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
        words = [w for name in names for w in spelling.display(name).split()]
        long = any(len(f"{n.given} {n.family}".split()) >= LONG_NAME for n in names)
        moved = name_tokens.is_title(part.partition(",")[0].strip()) or names == unscrambled(part)
        watched = any(spelling.fold(p) in WATCH_WORDS for w in words for p in w.split("-"))
        damaged = any(len(w) == 1 and w.islower() for w in words) or any(
            GLUED_BY_RE.fullmatch(n.given.split()[0]) for n in names
        )
        if names and (long or watched or moved or damaged):
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


def unused_parts(bylines: Iterable[str | None], decided: set[str]) -> list[str]:
    """List the decided parts that no byline holds any more.

    A change in how bylines are split leaves decisions that apply to nothing; they would
    still be counted as reviewed cases, so they are listed to be retired.
    """
    held = {part for byline in bylines for part in split_authors(byline)}
    return sorted(decided - held)


def _part_rows(parts: Counter, papers: dict[str, set[str]]) -> Table:
    rows = [
        [part, str(n), "/".join(sorted(papers[part])), _reading(part)]
        for part, n in sorted(parts.items())
    ]
    return [["part", "times", "newspapers", "read_now_as"], *rows]


def _reading(part: str) -> str:
    return "; ".join(spelling.display(name) for name in read_part(part)[0])


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
    names = author_cases.read(clean / "author_names.csv")
    keys = {row[names[0].index("name_key")] for row in names[1:]}
    judged = review.load_pairs(review_dir / review.PAIRS_FILE)
    signed = author_cases.by_variant(art, review.load_parts(review_dir / review.PARTS_FILE))
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
        "pairs_to_review": author_cases.pair_rows(clean, article),
        "merged_to_review": author_cases.suffix_merges(
            names, set(judged), author_cases.MIN_SUFFIX_MERGE
        ),
        "distant_to_review": author_cases.distant_merges(names, signed, set(judged)),
        "unused_parts": [
            ["part"],
            *([part] for part in unused_parts(every_byline.unique().to_pylist(), decided)),
        ],
        "unused_pairs": [["key_a", "key_b"], *map(list, author_cases.unused_pairs(judged, keys))],
    }
    for name, table in tables.items():
        write_csv(table, review_dir / "cases" / f"{name}.csv")
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
