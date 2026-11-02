"""Tests for econ_corpus.summaries and econ_corpus.datasheet on tiny synthetic tables."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus import datasheet, summaries, tables

NYT_ONLINE = "newyorktimes(online);newyork"
NYT_PRINT = "newyorktimes,lateedition(eastcoast);newyork,n.y."
WSJ = "wallstreetjournal(online);newyork,n.y."
BLOG = "blog,podcastositioweb"
PAPER = "periódicos"
DEFAULTS = {
    "publication_key": NYT_PRINT,
    "publication": "Example Daily; City",
    "source_type_key": PAPER,
    "author": "Doe, Jane",
    "pub_year": 2001,
    "doc_id": 1,
    "doc_type": "Commentary",
    "section": "Opinion",
    "language_key": "english",
    "source_file": "ProQuestDocuments-2024-11-22_1.txt",
    "date_status": "ok",
    "year_status": "ok",
    "id_status": "ok",
    "has_body": True,
    "title": "Sample title",
}


def make_articles(*rows: dict) -> dict[str, list]:
    """Build a dict of columns from row dicts; missing keys take the defaults."""
    full = [{**DEFAULTS, **row} for row in rows]
    return {key: [row[key] for row in full] for key in DEFAULTS}


# --- summaries helpers -------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (NYT_ONLINE, "New York Times"),
        (NYT_PRINT, "New York Times"),
        ("thewashingtonpost;washington,d.c.", "Washington Post"),
        ("laopinión;losangeles,calif.", "Other"),
        (None, None),
    ],
)
def test_newspaper_family(key: str | None, expected: str | None) -> None:
    assert summaries.newspaper_family(key) == expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (NYT_ONLINE, "online"),
        ("losangelestimes(pre-1997fulltext);losangeles,calif.", "pre-1997"),
        ("bostonglobe;boston,mass.", "print"),
    ],
)
def test_edition(key: str, expected: str) -> None:
    assert summaries.edition(key) == expected


def test_split_labels_handles_multi_label_and_missing() -> None:
    assert summaries.split_labels("Commentary, Opinions") == ["Commentary", "Opinions"]
    assert summaries.split_labels(None) == []


def test_download_date_comes_from_the_file_name() -> None:
    assert summaries.download_date("ProQuestDocuments-2024-12-04_1.txt") == "2024-12-04"
    assert summaries.download_date("notes.txt") is None


def test_pct_formats_and_guards_zero_total() -> None:
    assert summaries.pct(1, 3) == "33.3%"
    assert summaries.pct(0, 0) == "n/a"


def test_num_uses_thousands_separators() -> None:
    assert summaries.num(1234567) == "1,234,567"
    assert summaries.num(12) == "12"


# --- tables ------------------------------------------------------------------------


def test_md_table_renders_header_separator_and_rows() -> None:
    text = tables.md_table([["A", "B"], ["1", "2"]])
    assert text.splitlines() == ["| A | B |", "|---|---|", "| 1 | 2 |"]


def test_newspaper_table_splits_editions_blogs_and_authors() -> None:
    articles = make_articles(
        {"publication_key": NYT_ONLINE, "source_type_key": BLOG, "author": None},
        {"publication_key": NYT_ONLINE, "source_type_key": BLOG},
        {"publication_key": NYT_PRINT},
        {"publication_key": WSJ},
    )
    rows = {r[0]: r for r in tables.newspaper_table(articles)}
    header = tables.newspaper_table(articles)[0]
    nyt = dict(zip(header, rows["New York Times"], strict=True))
    assert nyt["Records"] == "3"
    assert nyt["Online"] == "2"
    assert nyt["Blog/podcast/website"] == "2"
    assert nyt["With author"] == "66.7%"
    assert rows["Wall Street Journal"][1] == "1"


def test_decade_table_counts_records_and_unique_ids() -> None:
    articles = make_articles(
        {"pub_year": 1995, "doc_id": 1},
        {"pub_year": 1995, "doc_id": 1},
        {"pub_year": 2004, "doc_id": 2},
        {"pub_year": None, "doc_id": 3},
    )
    rows = {r[0]: r for r in tables.decade_table(articles)[1:]}
    assert rows["1990s"][1:3] == ["2", "1"]
    assert rows["2000s"][1:3] == ["1", "1"]
    assert rows["Unknown year"][1] == "1"


def test_doc_type_table_counts_each_label_of_a_multi_label_value() -> None:
    articles = make_articles(
        {"doc_type": "Commentary, Opinions"},
        {"doc_type": "Commentary", "author": None},
    )
    rows = {r[0]: r for r in tables.doc_type_table(articles)[1:]}
    assert rows["Commentary"][1] == "2"
    assert rows["Opinions"][1] == "1"
    assert rows["Commentary"][2] == "50.0%"


def test_language_table_groups_spanish_and_missing() -> None:
    articles = make_articles(
        {"language_key": "english"},
        {"language_key": "spanish;english"},
        {"language_key": None},
    )
    rows = {r[0]: r[1] for r in tables.language_table(articles)[1:]}
    assert rows == {"English only": "1", "Includes Spanish": "1", "Missing": "1"}


def test_facts_report_duplicate_rows_and_unique_ids() -> None:
    articles = make_articles(
        {
            "doc_id": 1,
            "source_type_key": BLOG,
            "source_file": "ProQuestDocuments-2024-12-04_1.txt",
        },
        {"doc_id": 1, "source_file": "ProQuestDocuments-2024-12-31_1.txt"},
        {"doc_id": 2, "source_file": "ProQuestDocuments-2024-12-31_2.txt"},
    )
    facts = datasheet.facts(articles)
    assert facts["n_articles"] == "3"
    assert facts["n_unique_ids"] == "2"
    assert facts["n_duplicate_rows"] == "1"


def test_year_table_has_one_row_per_year() -> None:
    articles = make_articles({"pub_year": 2001}, {"pub_year": 2001}, {"pub_year": 2003})
    rows = tables.year_table(articles)
    assert rows[0][0] == "Year"
    assert [r[:2] for r in rows[1:]] == [["2001", "2"], ["2003", "1"]]


def test_section_table_groups_ignoring_case() -> None:
    articles = make_articles({"section": "Opinion"}, {"section": "OPINION"}, {"section": None})
    rows = tables.section_table(articles)
    assert rows[1] == ["opinion", "2", "66.7%"]


def test_missing_table_counts_each_field() -> None:
    articles = make_articles(
        {"title": None, "author": None, "date_status": "year_only", "has_body": False},
        {},
    )
    rows = {r[0]: r[1] for r in tables.missing_table(articles)[1:]}
    assert rows["Title"] == "1"
    assert rows["Author"] == "1"
    assert rows["Full publication date"] == "1"
    assert rows["Body text"] == "1"
    assert rows["Document id"] == "0"


def test_other_publications_table_uses_commonest_label_and_skips_queried_papers() -> None:
    other = "laopinión;losangeles,calif."
    articles = make_articles(
        {"publication_key": other, "publication": "La Opinión; Los Angeles"},
        {"publication_key": other, "publication": "La Opinión; Los Angeles"},
        {"publication_key": other, "publication": "La Opi nión; Los Angeles"},
        {"publication_key": NYT_PRINT},
    )
    assert tables.other_publications_table(articles)[1:] == [["La Opinión; Los Angeles", "3"]]


def test_download_table_counts_blogs_per_download_date() -> None:
    articles = make_articles(
        {
            "source_type_key": BLOG,
            "source_file": "ProQuestDocuments-2024-12-04_1.txt",
            "pub_year": 1990,
        },
        {"source_file": "ProQuestDocuments-2024-12-04_2.txt"},
        {"source_file": "ProQuestDocuments-2024-12-31_1.txt"},
    )
    assert tables.download_table(articles)[1:] == [
        ["2024-12-04", "2", "1", "50.0%", "1990", "2001"],
        ["2024-12-31", "1", "0", "0.0%", "2001", "2001"],
    ]


def test_build_writes_datasheet_and_csv_tables(tmp_path: Path) -> None:
    articles = make_articles({"doc_id": 1}, {"doc_id": 2})
    columns = {**articles, "is_footer": [False, False]}
    footer = {k: [None] for k in columns} | {"is_footer": [True]}
    merged = {k: columns[k] + footer[k] for k in columns}
    parquet = tmp_path / "records.parquet"
    pq.write_table(pa.table(merged), parquet)
    template = tmp_path / "template.md"
    template.write_text("Articles: {{n_articles}}\n\n{{newspapers}}\n", encoding="utf-8")
    values = tmp_path / "out" / "datasheet.md"
    values.parent.mkdir()
    datasheet.build(parquet, template, values, tmp_path / "tables")
    text = values.read_text(encoding="utf-8")
    assert text.startswith("Articles: 2\n")
    assert "| New York Times | 2 |" in text
    assert (tmp_path / "tables" / "raw_by_year.csv").exists()
    assert (tmp_path / "tables" / "raw_by_download_date.csv").exists()


def test_year_table_formats_large_counts_with_separators() -> None:
    articles = make_articles(*[{"pub_year": 2001, "doc_id": i} for i in range(1200)])
    assert tables.year_table(articles)[1][:3] == ["2001", "1,200", "1,200"]


def test_facts_count_records_outside_the_three_queried_document_types() -> None:
    articles = make_articles(
        {"doc_type": "Commentary, Opinions"},
        {"doc_type": "Opinions"},
        {"doc_type": "NEWSPAPER"},
        {"doc_type": None},
    )
    facts = datasheet.facts(articles)
    assert facts["n_outside_doc_types"] == "2"
    assert facts["outside_doc_types_pct"] == "50.0%"


def test_facts_derive_the_numbers_quoted_in_the_prose() -> None:
    articles = make_articles(
        {"publication_key": NYT_ONLINE, "source_type_key": BLOG},
        {"publication_key": NYT_PRINT, "language_key": "spanish;english"},
        {"publication_key": "laopinión;la", "doc_type": "Op-Ed", "has_body": False},
        {"publication_key": "dailynews;la", "doc_type": "Op-Ed", "has_body": False},
    )
    facts = datasheet.facts(articles)
    assert facts["english_only_pct"] == "75.0%"
    assert facts["n_other_publications"] == "2"
    assert facts["n_doc_type_labels"] == "2"
    assert facts["blog_online_pct"] == "100.0%"
    assert facts["blog_newspapers"] == "New York Times"
    assert "Star Tribune" in facts["missing_newspapers"]
    assert facts["n_queried_newspapers"] == "10"
    assert "New York Times" not in facts["missing_newspapers"]
    assert facts["n_no_body_files"] == "1"
    assert facts["download_first"] == facts["download_last"] == "2024-11-22"


def test_facts_separate_duplicates_across_files_from_duplicates_inside_a_file() -> None:
    articles = make_articles(
        {"doc_id": 1, "source_file": "ProQuestDocuments-2024-11-22_1.txt"},
        {"doc_id": 1, "source_file": "ProQuestDocuments-2024-11-22_2.txt"},
        {"doc_id": 2, "source_file": "ProQuestDocuments-2024-11-22_1.txt"},
        {"doc_id": 2, "source_file": "ProQuestDocuments-2024-11-22_1.txt"},
    )
    facts = datasheet.facts(articles)
    assert facts["n_ids_in_several_files"] == "1"
    assert facts["n_repeats_inside_a_file"] == "1"


def test_online_edition_table_reports_label_and_whether_it_ever_varies() -> None:
    articles = make_articles(
        {"publication_key": NYT_ONLINE, "source_type_key": BLOG, "pub_year": 1999},
        {"publication_key": NYT_ONLINE, "source_type_key": BLOG, "pub_year": 2005},
        {"publication_key": WSJ, "pub_year": 2010},
        {"publication_key": WSJ, "pub_year": 2010, "source_type_key": BLOG},
        {"publication_key": NYT_PRINT},
    )
    rows = {r[0]: r for r in tables.online_edition_table(articles)[1:]}
    assert rows["New York Times"] == ["New York Times", "2", "1999", "100.0%", "0"]
    assert rows["Wall Street Journal"] == ["Wall Street Journal", "2", "2010", "50.0%", "1"]
    assert "Boston Globe" not in rows


def test_blog_profile_table_counts_labels_of_blog_labelled_records_only() -> None:
    articles = make_articles(
        {"source_type_key": BLOG, "doc_type": "News"},
        {"source_type_key": BLOG, "doc_type": "News, Opinions"},
        {"source_type_key": PAPER, "doc_type": "Editorial"},
    )
    rows = tables.blog_profile_table(articles)
    assert rows[0] == ["Document type", "Blog-labelled records", "Share of blog-labelled"]
    assert rows[1:] == [["News", "2", "100.0%"], ["Opinions", "1", "50.0%"]]


def test_facts_report_opinion_sections_among_blog_labelled_records() -> None:
    articles = make_articles(
        {"source_type_key": BLOG, "section": "Opinion"},
        {"source_type_key": BLOG, "section": "Editorial-Opinion"},
        {"source_type_key": BLOG, "section": "Sports"},
        {"source_type_key": BLOG, "section": None},
        {"source_type_key": PAPER, "section": "Opinion"},
    )
    assert datasheet.facts(articles)["blog_opinion_section_pct"] == "50.0%"


# --- template ----------------------------------------------------------------------


def test_fill_replaces_placeholders() -> None:
    assert datasheet.fill("Rows: {{n}}.", {"n": "5"}) == "Rows: 5."


def test_fill_raises_on_unknown_placeholder() -> None:
    with pytest.raises(KeyError):
        datasheet.fill("{{missing}}", {"n": "5"})
