"""Tests for econ_corpus.clean.datasheet_clean on tiny synthetic tables (made-up names)."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus.clean import datasheet_clean, processed
from econ_corpus.raw import parse
from econ_corpus.raw.reasons import write_reasons

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
        reasons=["kept", "kept", "file_footer", "no_author"],
        parts=[
            {"replacement": "KEEP"},
            {"replacement": "NOBODY"},
            {"replacement": "Doe, Jane"},
            {"replacement": "unsure"},
        ],
        pairs=[{"decision": "same"}, {"decision": "different"}],
    )


def test_facts_count_the_tables_and_the_years() -> None:
    facts = datasheet_clean.facts(make_inputs())
    assert (facts["n_articles"], facts["n_authors"], facts["n_links"]) == ("2", "2", "3")
    assert (facts["year_min"], facts["year_max"], facts["n_newspapers"]) == ("1999", "2001", "2")


def test_facts_give_a_count_for_every_reason_and_for_the_raw_table() -> None:
    facts = datasheet_clean.facts(make_inputs())
    assert facts["n_parsed"] == "4"
    assert facts["n_file_footer"] == "1"
    assert facts["n_no_author"] == "1"
    assert facts["n_duplicate_id"] == "0"
    assert facts["n_raw"] == "3"


def test_facts_say_how_names_were_read_and_linked() -> None:
    facts = datasheet_clean.facts(make_inputs())
    assert (facts["n_links_recovered"], facts["n_links_manual"]) == ("1", "1")
    assert (facts["n_names"], facts["n_names_rule"], facts["n_names_review"]) == ("3", "1", "0")
    assert facts["one_author_pct"] == "50.0%"
    assert (facts["n_authors_one_article"], facts["authors_one_article_pct"]) == ("1", "50.0%")


def test_facts_count_the_manual_review_and_what_is_left() -> None:
    facts = datasheet_clean.facts(make_inputs())
    assert facts["n_review_parts"] == "4"
    assert (facts["n_parts_corrected"], facts["n_parts_nobody"]) == ("1", "1")
    assert (facts["n_parts_keep"], facts["n_parts_unsure"]) == ("1", "1")
    assert (facts["n_review_pairs"], facts["n_pairs_same"], facts["n_pairs_different"]) == (
        "2",
        "1",
        "1",
    )
    assert facts["n_pairs_unsure"] == "0"
    assert (facts["n_candidates"], facts["n_candidates_not_reviewed"]) == ("1", "1")


def test_build_writes_the_datasheet_the_flow_figure_and_the_flow_table(tmp_path: Path) -> None:
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
    codes = ["kept", "kept", "no_person_author", "file_footer"]
    write_reasons(pq.read_table(records), codes, reasons)
    clean = tmp_path / "clean"
    processed.build(records, reasons, clean)
    template = tmp_path / "template.md"
    template.write_text(
        "Articles: {{n_articles}}\nAuthors: {{n_authors}}\nNo person: {{n_no_person_author}}\n\n"
        "{{flow}}\n\n{{newspapers}}\n\n{{top_authors}}\n",
        encoding="utf-8",
    )
    out = tmp_path / "datasheet.md"
    datasheet_clean.build(
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
    assert text.startswith("Articles: 2\nAuthors: 2\nNo person: 1\n")
    assert "| Rows parsed |  |  | 4 |" in text
    assert "| New York Times | 2 |" in text
    assert "| Jane Doe | 2 |" in text
    assert (tmp_path / "figures" / "clean_flow.svg").read_text().startswith("<svg")
    assert (tmp_path / "tables" / "clean_flow.csv").exists()


def test_build_refuses_tables_that_do_not_match_the_reasons(tmp_path: Path) -> None:
    rows = [parse.empty_row("a.txt", i, is_footer=False) for i in range(2)]
    for i, row in enumerate(rows):
        row |= {"doc_id": 100 + i, "author": "Doe, Jane", "publication_key": NYT, "pub_year": 2020}
        row |= {"title": f"Title {i}", "text": "Synthetic body.", "has_body": True}
    records, reasons = tmp_path / "records.parquet", tmp_path / "exclusions.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=parse.SCHEMA), records)
    write_reasons(pq.read_table(records), ["kept", "no_author"], reasons)
    processed.build(records, reasons, tmp_path / "clean")
    write_reasons(pq.read_table(records), ["kept", "kept"], reasons)  # reasons move on
    template = tmp_path / "template.md"
    template.write_text("Articles: {{n_articles}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="processed"):
        datasheet_clean.build(
            tmp_path / "clean",
            records,
            reasons,
            tmp_path / "review",
            template=template,
            out_md=tmp_path / "out.md",
            tables_dir=tmp_path,
            figures_dir=tmp_path,
        )
