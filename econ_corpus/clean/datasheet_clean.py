"""Step 6 of the pipeline: describe the cleaned dataset and write its datasheet.

Input: the cleaned tables written by `processed`, the reasons written by `exclusions`, the
manual-review files and a prose template with {{placeholders}}.
Output: a markdown datasheet whose numbers all come from the data, the flow from the parsed
rows to the cleaned dataset as a table and as a figure.

Lives here: the headline numbers, the template filling and the file writing. Does not live
here: the tables (clean_tables), the figure (figures), the prose (the template, in docs/) or
any rule about records and authors.
"""

from collections import Counter
import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import pyarrow as pa
import pyarrow.csv as pacsv

from econ_corpus.clean import clean_tables, manifest
from econ_corpus.names import review
from econ_corpus.raw import datasheet
from econ_corpus.raw.reasons import LEFT_OUT, REASONS, load
from econ_corpus.shared import figures, summaries, tables

Rows = list[dict[str, str]]
AUTHORS_PER_ARTICLE = [("1", 1, 1), ("2", 2, 2), ("3", 3, 3), ("4", 4, 4), ("5 or more", 5, None)]
ARTICLES_PER_AUTHOR = [
    ("1", 1, 1),
    ("2 to 9", 2, 9),
    ("10 to 99", 10, 99),
    ("100 or more", 100, None),
]
TOP_AUTHORS = 15
HEADING = "From the ProQuest exports to the cleaned dataset"


@dataclass
class Inputs:
    """Everything the datasheet is computed from, already read from disk."""

    authors: Rows
    names: Rows
    links: Rows
    candidates: Rows
    newspapers: list[str]
    editions: list[str]
    years: list[int | None]
    reasons: list[str]
    parts: Rows
    pairs: Rows


def facts(inputs: Inputs) -> dict[str, str]:
    """Return the headline numbers quoted in the prose of the datasheet."""
    reasons = Counter(inputs.reasons)
    read = Counter(link["read"] for link in inputs.links)
    rules = Counter(name["rule"] for name in inputs.names)
    reviewed = Counter(c["review"] for c in inputs.candidates)
    per_article = Counter(link["doc_id"] for link in inputs.links)
    one_author = sum(n == 1 for n in per_article.values())
    one_article = sum(a["articles"] == "1" for a in inputs.authors)
    years = [y for y in inputs.years if y]
    n_articles, n_links, n_authors = len(inputs.newspapers), len(inputs.links), len(inputs.authors)
    counts = {
        "n_parsed": len(inputs.reasons),
        "n_raw": sum(n for code, n in reasons.items() if code not in LEFT_OUT),
        "n_articles": n_articles,
        "n_authors": n_authors,
        "n_links": n_links,
        "n_newspapers": len(set(inputs.newspapers)),
        "n_links_as_written": read["as_written"],
        "n_links_recovered": read["recovered"],
        "n_links_manual": read["manual_review"],
        "n_names": len(inputs.names),
        "n_names_rule": rules["shared_newspaper"],
        "n_names_review": rules["manual_review"],
        "n_candidates": len(inputs.candidates),
        "n_candidates_not_reviewed": reviewed["not_reviewed"],
        "n_candidates_different": reviewed["different"],
        "n_candidates_unsure": reviewed["unsure"],
        "n_authors_one_article": one_article,
    } | {f"n_{r['code']}": reasons[r["code"]] for r in REASONS}
    shares = {
        "one_author_pct": summaries.pct(one_author, n_articles),
        "authors_one_article_pct": summaries.pct(one_article, n_authors),
        "links_as_written_pct": summaries.pct(read["as_written"], n_links),
        "year_min": str(min(years)),
        "year_max": str(max(years)),
    }
    numbers = {name: summaries.num(n) for name, n in counts.items()}
    outcomes = review.outcome_counts(inputs.parts, inputs.pairs)
    return numbers | shares | {name: summaries.num(n) for name, n in outcomes.items()}


def described(inputs: Inputs) -> dict[str, tables.Table]:
    """Return the tables shown in the datasheet."""
    per_article = Counter(link["doc_id"] for link in inputs.links).values()
    top = sorted(inputs.authors, key=lambda a: -int(a["articles"]))[:TOP_AUTHORS]
    kinds = [f"{c['kind']} / {c['review']}" for c in inputs.candidates]
    return {
        "flow": clean_tables.flow_table(clean_tables.flow(inputs.reasons)),
        "newspapers": clean_tables.newspaper_table(inputs.newspapers, inputs.editions),
        "decades": clean_tables.decade_table(inputs.years),
        "authors_per_article": clean_tables.binned_table(
            per_article, AUTHORS_PER_ARTICLE, "Authors", "Articles"
        ),
        "articles_per_author": clean_tables.binned_table(
            (int(a["articles"]) for a in inputs.authors),
            ARTICLES_PER_AUTHOR,
            "Articles",
            "Authors",
        ),
        "read": clean_tables.counts_table((link["read"] for link in inputs.links), "Read"),
        "candidate_kinds": clean_tables.counts_table(kinds, "Kind / review"),
        "top_authors": [
            ["Author", "Articles"],
            *([a["name"], summaries.num(int(a["articles"]))] for a in top),
        ],
    }


def _rows(path: Path) -> Rows:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_inputs(clean: Path, records: Path, reasons_file: Path, review_dir: Path) -> Inputs:
    """Read the cleaned tables, the reasons and the review files.

    The three must belong together: the reasons must have been computed from these records
    and with these review files, and the cleaned tables must have been built from both.
    Otherwise the datasheet would mix two states of the pipeline.
    """
    review.same_review(reasons_file, review.load_parts(review_dir / review.PARTS_FILE))
    manifest.check(clean, records, reasons_file, review_dir)
    codes = load(records, reasons_file).to_pylist()
    columns = ["newspaper", "edition", "pub_year"]
    art = pacsv.read_csv(
        clean / "articles.csv",
        parse_options=pacsv.ParseOptions(newlines_in_values=True),
        convert_options=pacsv.ConvertOptions(
            include_columns=columns, column_types={"pub_year": pa.int64()}
        ),
    ).to_pydict()
    return Inputs(
        authors=_rows(clean / "authors.csv"),
        names=_rows(clean / "author_names.csv"),
        links=_rows(clean / "article_authors.csv"),
        candidates=_rows(clean / "author_candidates.csv"),
        newspapers=art["newspaper"],
        editions=art["edition"],
        years=art["pub_year"],
        reasons=codes,
        parts=_rows(review_dir / review.PARTS_FILE),
        pairs=_rows(review_dir / review.PAIRS_FILE),
    )


def build(  # noqa: PLR0913 (one argument per input or output file)
    clean: Path,
    records: Path,
    reasons_file: Path,
    review_dir: Path,
    *,
    template: Path,
    out_md: Path,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    """Read the cleaned dataset, fill the template and write the datasheet and the flow."""
    inputs = read_inputs(clean, records, reasons_file, review_dir)
    shown = described(inputs)
    values = facts(inputs) | {name: tables.md_table(rows) for name, rows in shown.items()}
    out_md.write_text(
        datasheet.fill(template.read_text(encoding="utf-8"), values), encoding="utf-8"
    )
    tables.write_csv(shown["flow"], tables_dir / "clean_flow.csv")
    figures_dir.mkdir(parents=True, exist_ok=True)
    steps = clean_tables.flow(inputs.reasons)
    chart = figures.flow_svg(steps, start=len(inputs.reasons), heading=HEADING)
    (figures_dir / "clean_flow.svg").write_text(chart, encoding="utf-8")


def main() -> None:
    """Build the datasheet of the cleaned dataset from the repo's default locations."""
    build(
        Path("data/processed/clean"),
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        review.folder(Path("data/review")),
        template=Path("docs/datasheet_clean.template.md"),
        out_md=Path("docs/datasheet_clean.md"),
        tables_dir=Path("reports/tables"),
        figures_dir=Path("reports/figures"),
    )


if __name__ == "__main__":
    main()
