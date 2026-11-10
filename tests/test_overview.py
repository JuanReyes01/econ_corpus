"""Tests for econ_corpus.overview on tiny synthetic tables (made-up names)."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from econ_corpus import overview
from econ_corpus.clean import datasheet_clean, processed
from econ_corpus.raw import datasheet, parse
from econ_corpus.raw.reasons import write_reasons
from econ_corpus.shared import tables
from econ_corpus.shared.figures import MINUS

NYT = "newyorktimes,lateedition(eastcoast);newyork,n.y."


def make_inputs() -> datasheet_clean.Inputs:
    return datasheet_clean.Inputs(
        authors=[
            {"author_id": "1", "name": "Jane Doe", "articles": "2", "name_variants": "2"},
            {"author_id": "2", "name": "Richard Roe", "articles": "1", "name_variants": "1"},
        ],
        names=[{"rule": "main"}, {"rule": "shared_newspaper"}, {"rule": "main"}],
        links=[
            {"doc_id": "10", "author_id": "1", "read": "as_written"},
            {"doc_id": "10", "author_id": "2", "read": "recovered"},
            {"doc_id": "11", "author_id": "1", "read": "manual_review"},
        ],
        candidates=[{"kind": "one_letter_apart", "review": "not_reviewed"}],
        newspapers=["New York Times", "Boston Globe"],
        editions=["print", "online"],
        years=[1999, 2001],
        reasons=[
            "kept",
            "kept",
            "file_footer",
            "file_footer",
            "duplicate_id",
            "no_author",
            "no_text",
        ],
        parts=[{"replacement": "KEEP"}, {"replacement": "NOBODY"}],
        pairs=[{"decision": "same"}],
    )


def test_facts_count_the_files_the_rows_and_what_each_pipeline_leaves_out() -> None:
    facts = overview.facts(make_inputs())
    assert facts["n_files"] == "2"  # one footer per export file
    assert facts["n_parsed"] == "7"
    assert facts["n_raw"] == "4"  # 7 rows less two footers and one repeated id
    assert facts["n_left_raw"] == "3"
    assert facts["n_left_clean"] == "2"  # one unsigned, one without text
    assert facts["n_articles"] == "2"  # the facts of the cleaned datasheet come along
    assert facts["n_review_parts"] == "2"


def test_the_lanes_of_the_map_name_the_steps_and_carry_the_counts() -> None:
    lanes = overview.lanes(overview.facts(make_inputs()))
    assert len(lanes) == 3  # the two pipelines and the manual review that feeds them
    names = [box.name for lane in lanes for box in lane.boxes]
    for module in ("parse", "exclusions", "export", "processed", "review_cases"):
        assert module in names
    roles = " ".join(box.role for lane in lanes for box in lane.boxes)
    assert "2 files" in roles
    assert "4 records" in roles
    assert "2 articles" in roles
    labels = " ".join(label for lane in lanes for label in lane.arrows)
    assert "7 rows" in labels
    assert f"{MINUS} 3" in labels  # left out by pipeline 1
    assert f"{MINUS} 2" in labels  # left out by pipeline 2
    for lane in lanes:
        assert len(lane.arrows) == len(lane.boxes) - 1
        assert len(lane.boxes) <= overview.pipeline_figure.BOXES
        assert all(len(box.role.split("\n")) <= 2 for box in lane.boxes)


def test_the_real_template_has_no_unknown_placeholder() -> None:
    inputs = make_inputs()
    values = overview.facts(inputs) | {
        name: tables.md_table(rows) for name, rows in overview.described(inputs).items()
    }
    template = Path("docs/datasheet.template.md").read_text(encoding="utf-8")
    filled = datasheet.fill(template, values)  # KeyError on a placeholder nothing gives
    assert "{{" not in filled
    assert "| ProQuest export files | 2 |" in filled


def test_build_writes_the_overview_its_figures_and_its_tables(tmp_path: Path) -> None:
    rows = []
    for i, byline in enumerate(
        ["Doe, Jane", "Roe, Richard; Doe, Jane", "The Editorial Board", None]
    ):
        row = parse.empty_row("a.txt", i, is_footer=byline is None)
        if byline:
            row |= {"doc_id": 100 + i, "author": byline, "publication_key": NYT, "pub_year": 2020}
            row |= {"title": f"Title {i}", "text": "Synthetic body.", "has_body": True}
        rows.append(row)
    records, reasons = tmp_path / "records.parquet", tmp_path / "exclusions.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    write_reasons(
        pq.read_table(records), ["kept", "kept", "no_person_author", "file_footer"], reasons
    )
    clean = tmp_path / "clean"
    processed.build(records, reasons, clean)
    template = tmp_path / "template.md"
    template.write_text(
        "Files: {{n_files}}\nParsed: {{n_parsed}}\nArticles: {{n_articles}}\n\n"
        "{{flow}}\n\n{{authors_per_article}}\n",
        encoding="utf-8",
    )
    out = tmp_path / "datasheet.md"
    overview.build(
        clean,
        records,
        reasons,
        tmp_path / "review",
        template=template,
        out_md=out,
        tables_dir=tmp_path / "tables",
        figures_dir=tmp_path / "figures",
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith("Files: 1\nParsed: 4\nArticles: 2\n")
    assert "| Rows parsed |  |  | 4 |" in text  # the full flow, both pipelines
    assert "| file_footer |" in text
    for name in overview.FIGURES:
        svg = (tmp_path / "figures" / f"{name}.svg").read_text(encoding="utf-8")
        assert svg.startswith("<svg"), name
    assert "parse" in (tmp_path / "figures" / "pipeline.svg").read_text(encoding="utf-8")
    assert (tmp_path / "tables" / "pipeline_flow.csv").exists()
    assert (tmp_path / "tables" / "clean_by_year.csv").exists()
