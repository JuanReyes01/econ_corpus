"""Step 3b of the pipeline: describe the raw table and write its datasheet.

Input: the parquet written by `parse`, the reasons written by `exclusions` and a prose
template with {{placeholders}}.
Output: a markdown datasheet whose numbers all come from the data, plus yearly and
per-download tables as CSV, so every figure in the text can be reproduced.

The shared raw table leaves out footers, repeated ids and repeated text, so the tables describe
that table;
the repeats, the yearly counts and the download dates describe the table as parsed.

Lives here: the template filling and the file writing. Does not live here: the headline
numbers (headline), the tables themselves (tables), the prose (the template, in docs/) or
any decision about which records to keep (exclusions).
"""

from collections import Counter
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from econ_corpus.raw import headline
from econ_corpus.raw.reasons import LEFT_OUT, load
from econ_corpus.shared import figures, source_tables, summaries, tables

COLUMNS = [
    "publication_key", "publication", "source_type_key", "author", "pub_year", "doc_id",
    "doc_type", "section", "language_key", "source_file", "date_status", "year_status",
    "id_status", "has_body", "title", "is_footer",
]  # fmt: skip


def fill(template: str, values: dict[str, str]) -> str:
    """Replace every {{name}} with its value; an unknown name raises KeyError."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], template)


def build(  # noqa: PLR0913 (one argument per input or output file)
    parquet: Path,
    reasons: Path,
    template: Path,
    out_md: Path,
    *,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    """Read the parquet, fill the template and write the datasheet and the CSV tables."""
    table = pq.read_table(parquet, columns=COLUMNS)
    codes = load(parquet, reasons)
    in_raw = pc.invert(pc.is_in(codes, value_set=pa.array(LEFT_OUT)))
    parsed = table.filter(pc.invert(table["is_footer"])).to_pydict()
    articles = table.filter(in_raw).to_pydict()
    described = {
        "newspapers": tables.newspaper_table(articles),
        "online_editions": source_tables.online_edition_table(articles),
        "blog_profile": tables.blog_profile_table(articles),
        "decades": tables.decade_table(articles),
        "doc_types": tables.doc_type_table(articles),
        "sections": tables.section_table(articles),
        "languages": tables.language_table(articles),
        "missing": tables.missing_table(articles),
        "other_publications": source_tables.other_publications_table(articles),
    }
    as_parsed = {k: v for k, v in headline.facts(parsed).items() if k in headline.PARSED_FACTS}
    footers = {"n_footer_rows": summaries.num(pc.sum(table["is_footer"]).as_py())}
    values = (
        headline.facts(articles)
        | as_parsed
        | headline.repeat_facts(parsed, Counter(codes.to_pylist()))
        | footers
        | {name: tables.md_table(rows) for name, rows in described.items()}
    )
    out_md.write_text(fill(template.read_text(encoding="utf-8"), values), encoding="utf-8")
    tables.write_csv(tables.year_table(parsed), tables_dir / "raw_by_year.csv")
    tables.write_csv(source_tables.download_table(parsed), tables_dir / "raw_by_download_date.csv")
    figures_dir.mkdir(parents=True, exist_ok=True)
    shared_chart = figures.year_chart_svg(
        tables.year_table(articles),
        labels=("Records",),
        heading="Records per publication year in the shared table",
    )
    (figures_dir / "records_by_year.svg").write_text(shared_chart, encoding="utf-8")
    repeats_chart = figures.year_chart_svg(
        tables.year_comparison_table(parsed, articles),
        labels=("As parsed", "Shared table"),
        heading="Records per publication year, as parsed and in the shared table",
    )
    (figures_dir / "repeats_by_year.svg").write_text(repeats_chart, encoding="utf-8")


def main() -> None:
    """Build the datasheet of the raw table from the repo's default locations."""
    build(
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        Path("docs/datasheet_raw.template.md"),
        Path("docs/datasheet_raw.md"),
        tables_dir=Path("reports/tables"),
        figures_dir=Path("reports/figures"),
    )


if __name__ == "__main__":
    main()
