"""Step 6b of the pipeline: the overview datasheet of both pipelines, figures first.

Input: the cleaned tables, the reasons of every parsed row, the review files and a prose
template with {{placeholders}}, the same inputs as the datasheet of the cleaned dataset.
Output: a short markdown document that maps the two pipelines, follows every parsed row to
the dataset it ends in and shows the main counts, with its figures and tables in reports/.

Lives here: the numbers quoted in the overview, the content of the map and the file writing.
Does not live here: the drawing (shared/figures, shared/pipeline_figure), the tables
(clean/clean_tables), the prose (the template, in docs/) or any rule about the records.
"""

from collections import Counter
from pathlib import Path

from econ_corpus.clean import clean_tables, datasheet_clean
from econ_corpus.names import review
from econ_corpus.raw import datasheet
from econ_corpus.raw.reasons import LEFT_OUT
from econ_corpus.shared import figures, pipeline_figure, summaries, tables
from econ_corpus.shared.pipeline_figure import Box, Lane

MINUS = figures.MINUS
FIGURES = ("pipeline", "pipeline_flow", "clean_by_year", "clean_by_newspaper")
MAP_HEADING = "The two pipelines, their steps and what passes between them"
FLOW_HEADING = "Where every parsed row ends: one reason each"


def facts(inputs: datasheet_clean.Inputs) -> dict[str, str]:
    """Return the numbers quoted in the overview.

    Those of the cleaned datasheet, plus the files, the rows parsed and what each pipeline
    leaves out.
    """
    reasons = Counter(inputs.reasons)
    n_parsed = len(inputs.reasons)
    n_raw = sum(n for code, n in reasons.items() if code not in LEFT_OUT)
    counts = {
        "n_files": reasons["file_footer"],  # every export file ends in one footer
        "n_parsed": n_parsed,
        "n_left_raw": n_parsed - n_raw,
        "n_left_clean": n_raw - len(inputs.newspapers),
    }
    return datasheet_clean.facts(inputs) | {k: summaries.num(v) for k, v in counts.items()}


def lanes(values: dict[str, str]) -> list[Lane]:
    """Return the map of the pipelines: one lane each, and one for the manual review."""
    raw_table = Box("Raw table", f"{values['n_raw']} records", "data")
    cleaned = Box(
        "Cleaned dataset",
        f"{values['n_articles']} articles\n{values['n_authors']} authors",
        "data",
    )
    return [
        Lane(
            "Pipeline 1: from the ProQuest exports to the raw table",
            [
                Box("ProQuest exports", f"{values['n_files']} files", "data"),
                Box("parse", "one row per record,\nevery field", "step"),
                Box("exclusions", "one reason\nper row", "step"),
                Box("export", "the raw table\nas CSV", "step"),
                raw_table,
            ],
            [
                "",
                f"{values['n_parsed']} rows",
                f"{MINUS} {values['n_left_raw']}\nfooters and repeats",
                "",
            ],
        ),
        Lane(
            "Pipeline 2: from the raw table to the cleaned dataset",
            [
                raw_table,
                Box("exclusions", "opinion, text,\na person as author", "step"),
                Box("processed", "bylines to authors\n(names); five tables", "step"),
                cleaned,
            ],
            ["", f"{MINUS} {values['n_left_clean']}\nFigure 2", ""],
        ),
        Lane(
            "Manual review: the decisions feed the next run of both pipelines",
            [
                cleaned,
                Box("review_cases", "doubtful bylines,\nlook-alike pairs", "step"),
                Box(
                    "data/review",
                    f"{values['n_review_parts']} parts\n{values['n_review_pairs']} pairs",
                    "data",
                ),
                Box("names/review", "applies the decisions\nin both pipelines", "step"),
            ],
            ["lists", "decided by\na language model", ""],
        ),
    ]


def described(inputs: datasheet_clean.Inputs) -> dict[str, tables.Table]:
    """Return the tables shown in the overview."""
    shown = datasheet_clean.described(inputs)
    return {
        "flow": clean_tables.flow_table(clean_tables.flow(inputs.reasons), start="Rows parsed"),
        "newspapers": shown["newspapers"],
        "authors_per_article": shown["authors_per_article"],
        "articles_per_author": shown["articles_per_author"],
        "by_year": clean_tables.year_table(inputs.years),
    }


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
    """Read the dataset, fill the template and write the overview with its figures."""
    inputs = datasheet_clean.read_inputs(clean, records, reasons_file, review_dir)
    values = facts(inputs)
    shown = described(inputs)
    filled = values | {name: tables.md_table(rows) for name, rows in shown.items()}
    out_md.write_text(datasheet.fill(template.read_text(encoding="utf-8"), filled), "utf-8")
    tables.write_csv(shown["flow"], tables_dir / "pipeline_flow.csv")
    tables.write_csv(shown["by_year"], tables_dir / "clean_by_year.csv")
    figures_dir.mkdir(parents=True, exist_ok=True)
    drawn = {
        "pipeline": pipeline_figure.pipeline_svg(lanes(values), heading=MAP_HEADING),
        "pipeline_flow": figures.flow_svg(
            clean_tables.flow(inputs.reasons), start_name="Rows parsed", heading=FLOW_HEADING
        ),
        "clean_by_year": figures.year_chart_svg(
            shown["by_year"],
            labels=("Articles",),
            heading="Articles per publication year in the cleaned dataset",
        ),
        "clean_by_newspaper": figures.bar_chart_svg(
            shown["newspapers"], heading="Articles per newspaper in the cleaned dataset"
        ),
    }
    for name in FIGURES:
        (figures_dir / f"{name}.svg").write_text(drawn[name], encoding="utf-8")


def main() -> None:
    """Build the overview from the repo's default locations."""
    build(
        Path("data/processed/clean"),
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        review.folder(Path("data/review")),
        template=Path("docs/datasheet.template.md"),
        out_md=Path("docs/datasheet.md"),
        tables_dir=Path("reports/tables"),
        figures_dir=Path("reports/figures"),
    )


if __name__ == "__main__":
    main()
