"""Tests for shared.summaries and raw.datasheet of econ_corpus on tiny synthetic tables."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus.raw import datasheet, parse
from econ_corpus.raw.reasons import write_reasons
from econ_corpus.shared import summaries, tables

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


@pytest.mark.parametrize(
    "section",
    [
        "Letters to the Editor",
        "Metro; Part-B; Op Ed Desk",
        "Op- Ed",
        "Viewpoints",
        "Perspective",
        "Commentary",
        "EDITORIAL-OPINION",
        "EPg",  # the editorial page of the Boston Globe before 1997
    ],
)
def test_opinion_sections_are_recognised_despite_spacing_and_wording(section: str) -> None:
    assert summaries.is_opinion_section(section)


@pytest.mark.parametrize("section", ["Sports", "Metro; Part-B; Metro Desk", "A", None])
def test_other_sections_are_not_opinion(section: str | None) -> None:
    assert not summaries.is_opinion_section(section)


@pytest.mark.parametrize(
    "title",
    [
        "REVIEW & OUTLOOK (Editorial): The Verity Mission",
        "Opinion Today: How worried should you really be about inflation?",
        "What Does Donald Trump Mean to You?:   [Op-Ed ]",
        "Letters to the Editor: Pakistan Needs Democracy",
        "Notable & Quotable",
        "Board of Contributors: Education Reforms That Do and Don't Work",
        "The Journal Editorial Report on FOX News Channel",
        "Asides: Hillary's Buffalo Voters",
        "REVIEW & OUT LOOK (Edi torial) -- Asides: Tax Freedom Day",
    ],
)
def test_opinion_titles_are_recognised(title: str) -> None:
    assert summaries.is_opinion_title(title)


@pytest.mark.parametrize(
    "title",
    [
        "World News: Unofficial Count Favors Jakarta Governor",
        "American Opinion (A Special Report): A Quarterly Survey",
        "US/WORLD NEWS IN BRIEF; POLL: OPINION OF UN DECLINES",
        "Politics & Economics: Cairo's Litigious Cleric",
        None,
    ],
)
def test_other_titles_are_not_opinion(title: str | None) -> None:
    assert not summaries.is_opinion_title(title)


@pytest.mark.parametrize(
    "title",
    ["TOON-OP; Laughing matters", "Op-Comic: A sample", "to on-op;", "TOON OP; x", "Op Comic: x"],
)
def test_cartoon_labels_at_the_start_of_a_title_are_recognised(title: str) -> None:
    assert summaries.is_cartoon_title(title)


@pytest.mark.parametrize("title", ["Cartoon warfare", "A word on the op-comic", "Op-Art: x", None])
def test_other_titles_are_not_cartoons(title: str | None) -> None:
    assert not summaries.is_cartoon_title(title)


def test_is_opinion_label() -> None:
    assert summaries.is_opinion_label("Op-Ed")
    assert summaries.is_opinion_label("Edi torial")
    assert summaries.is_opinion_label("Op - Ed")
    assert summaries.is_opinion_label("Letter To The Editor")
    assert not summaries.is_opinion_label("NEWSPAPER")


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


def test_decade_table_counts_records_and_signed_share_per_decade() -> None:
    articles = make_articles(
        {"pub_year": 1995, "doc_id": 1},
        {"pub_year": 1995, "doc_id": 2, "author": None},
        {"pub_year": 2004, "doc_id": 3},
        {"pub_year": None, "doc_id": 4},
    )
    rows = tables.decade_table(articles)
    # Ids are unique in the shared table, so the decade table has no id column.
    assert rows[0] == ["Decade", "Records", "With author"]
    assert rows[1:] == [
        ["1990s", "2", "50.0%"],
        ["2000s", "1", "100.0%"],
        ["Unknown year", "1", "100.0%"],
    ]


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


def test_year_comparison_table_sets_parsed_records_next_to_shared_records() -> None:
    parsed = make_articles({"pub_year": 2001}, {"pub_year": 2001}, {"pub_year": 2002})
    shared = make_articles({"pub_year": 2001}, {"pub_year": 2002})
    assert tables.year_comparison_table(parsed, shared) == [
        ["Year", "As parsed", "Shared table"],
        ["2001", "2", "1"],
        ["2002", "1", "1"],
    ]


def test_year_comparison_table_gives_zero_for_a_year_with_no_shared_record() -> None:
    parsed = make_articles({"pub_year": 2001}, {"pub_year": 2003})
    shared = make_articles({"pub_year": 2001})
    rows = tables.year_comparison_table(parsed, shared)
    assert rows[2] == ["2003", "1", "0"]


def test_year_table_has_one_row_per_year() -> None:
    articles = make_articles({"pub_year": 2001}, {"pub_year": 2001}, {"pub_year": 2003})
    rows = tables.year_table(articles)
    assert rows[0][0] == "Year"
    assert [r[:2] for r in rows[1:]] == [["2001", "2"], ["2003", "1"]]


def test_section_table_groups_spellings_of_one_label() -> None:
    articles = make_articles(
        {"section": "Opinion"}, {"section": "OPINION"}, {"section": "Opin ion"}, {"section": None}
    )
    rows = tables.section_table(articles)
    assert rows[1:] == [["Opinion", "3", "75.0%"]]


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


def test_build_describes_the_shared_table_and_counts_what_was_removed(tmp_path: Path) -> None:
    articles = make_articles(
        {"doc_id": 1},
        {"doc_id": 1, "has_body": False, "source_file": "ProQuestDocuments-2024-11-23_1.txt"},
        {"doc_id": 2},
        {"doc_id": 3},
    )
    columns = {**articles, "is_footer": [False] * 4, "record_index": [0, 1, 2, 3]}
    # The other columns a reason is decided from, which the reasons file is tied to.
    columns |= {"body_sha256": ["aaa"] * 4, "pub_date": ["2001-01-02"] * 4}
    columns |= {"body_chars": [100] * 4, "body_words": [20] * 4}
    footer = {k: [None] for k in columns} | {"is_footer": [True], "record_index": [4]}
    merged = {k: columns[k] + footer[k] for k in columns}
    parquet = tmp_path / "records.parquet"
    pq.write_table(pa.table(merged).replace_schema_metadata(parse.stamp()), parquet)
    reasons = tmp_path / "exclusions.parquet"
    codes = ["kept", "duplicate_id", "kept", "duplicate_text", "file_footer"]
    keys = {"source_file": merged["source_file"], "record_index": merged["record_index"]}
    write_reasons(pq.read_table(parquet), codes, reasons)
    other = tmp_path / "other.parquet"
    pq.write_table(pa.table({**keys, "record_index": [9, 8, 7, 6, 5], "reason": codes}), other)
    with pytest.raises(ValueError, match="rows"):
        datasheet.build(
            parquet,
            other,
            tmp_path / "t.md",
            tmp_path / "o.md",
            tables_dir=tmp_path,
            figures_dir=tmp_path,
        )
    template = tmp_path / "template.md"
    template.write_text(
        "Articles: {{n_articles}}\nParsed: {{n_parsed}}\nRemoved: {{n_repeats_removed}}\n"
        "Footers: {{n_footer_rows}}\nEmpty copies: {{n_ids_with_empty_copy}}\n"
        "Repeats: {{n_duplicate_rows}}\nSame text: {{n_text_repeats_removed}}\n"
        "Ids parsed: {{n_ids_parsed}}\nFiles: {{n_files}}\nFirst: {{download_first}}\n"
        "Last: {{download_last}}\n\n{{newspapers}}\n",
        encoding="utf-8",
    )
    values = tmp_path / "out" / "datasheet.md"
    values.parent.mkdir()
    datasheet.build(
        parquet,
        reasons,
        template,
        values,
        tables_dir=tmp_path / "tables",
        figures_dir=tmp_path / "figures",
    )
    text = values.read_text(encoding="utf-8")
    head = (
        "Articles: 2\nParsed: 4\nRemoved: 1\nFooters: 1\nEmpty copies: 1\nRepeats: 1\n"
        "Same text: 1\nIds parsed: 3\nFiles: 2\n"
    )
    assert text.startswith(head)
    assert "First: 2024-11-22\nLast: 2024-11-23\n" in text
    assert "| New York Times | 2 |" in text
    assert (tmp_path / "figures" / "records_by_year.svg").read_text().startswith("<svg")
    assert (tmp_path / "figures" / "repeats_by_year.svg").read_text().startswith("<svg")
    # Years and downloads describe the table as parsed, so the repeated rows still show.
    by_year = (tmp_path / "tables" / "raw_by_year.csv").read_text().splitlines()
    assert by_year[1].startswith("2001,4,3,")
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


def test_document_type_labels_are_counted_one_by_one_without_stray_spaces() -> None:
    articles = make_articles(
        {"doc_type": "News"},
        {"doc_type": "New s"},
        {"doc_type": "Commentary, NEWS"},
        {"doc_type": None},
    )
    facts = datasheet.facts(articles)
    assert facts["n_doc_type_labels"] == "2"
    assert facts["n_outside_doc_types"] == "0"


def test_file_order_reads_both_ways_of_numbering_downloads() -> None:
    names = [
        "ProQuestDocuments-2024-12-11 (2).txt",
        "ProQuestDocuments-2024-12-11.txt",
        "ProQuestDocuments-2024-12-11 (1).txt",
        "ProQuestDocuments-2024-12-11_3.txt",
    ]
    assert sorted(names, key=summaries.file_order) == [
        "ProQuestDocuments-2024-12-11.txt",
        "ProQuestDocuments-2024-12-11 (1).txt",
        "ProQuestDocuments-2024-12-11 (2).txt",
        "ProQuestDocuments-2024-12-11_3.txt",
    ]


def test_document_type_table_groups_spellings_of_one_label() -> None:
    articles = make_articles(
        {"doc_type": "News"}, {"doc_type": "New s"}, {"doc_type": "NEWS"}, {"doc_type": "News"}
    )
    assert tables.doc_type_table(articles)[1:] == [["News", "4", "100.0%"]]


def test_newsday_of_another_country_is_not_the_queried_newsday() -> None:
    assert summaries.newspaper_family("newsday,combinededitions;longisland,n.y.") == "Newsday"
    assert summaries.newspaper_family("newsday;bulawayo,zimbabwe") == "Other"


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


def test_facts_find_the_year_inflated_by_repeated_downloads() -> None:
    def row(year: int, doc_id: int, file_no: int) -> dict:
        return {
            "pub_year": year,
            "doc_id": doc_id,
            "source_file": f"ProQuestDocuments-2024-11-22_{file_no}.txt",
        }

    articles = make_articles(
        row(2005, 1, 1), row(2005, 1, 2), row(2005, 1, 3), row(2005, 2, 1), row(2006, 3, 1)
    )
    facts = datasheet.facts(articles)
    assert facts["dup_peak_year"] == "2005"
    assert facts["dup_peak_rows"] == "4"
    assert facts["dup_peak_unique"] == "2"
    assert facts["dup_peak_multi_file_pct"] == "50.0%"


def test_facts_count_news_labelled_records_by_opinion_signals() -> None:
    articles = make_articles(
        {"doc_type": "Commentary", "section": "Opinion"},
        {"doc_type": "NEWSPAPER", "section": "Opinion"},
        {"doc_type": "News", "section": "Sports"},
        {"doc_type": None, "section": None},
    )
    facts = datasheet.facts(articles)
    assert facts["news_label_opinion_section_pct"] == "25.0%"
    assert facts["no_opinion_signal_n"] == "2"
    assert facts["no_opinion_signal_pct"] == "50.0%"


def test_every_table_column_is_documented_in_the_template() -> None:
    template = (Path(__file__).parents[1] / "docs" / "datasheet_raw.template.md").read_text(
        encoding="utf-8"
    )
    missing = [name for name in parse.SCHEMA.names if f"`{name}`" not in template]
    assert not missing


# --- template ----------------------------------------------------------------------


def test_fill_replaces_placeholders() -> None:
    assert datasheet.fill("Rows: {{n}}.", {"n": "5"}) == "Rows: 5."


def test_fill_raises_on_unknown_placeholder() -> None:
    with pytest.raises(KeyError):
        datasheet.fill("{{missing}}", {"n": "5"})


@pytest.mark.parametrize(
    "title",
    [
        "LONG ISLAND OPINION; A Sample Title",
        "NEW JERSEY OPINION; A Sample Title",
        "CONNECITCUT OPINION; A SAMPLE TITLE",
        "OPINION; A SAMPLE TITLE",
        "Op-Ed: A sample title",
        "COMMENTARY; A sample title",
    ],
)
def test_opinion_page_headings_in_titles_are_recognised(title: str) -> None:
    assert summaries.is_opinion_title(title)


@pytest.mark.parametrize(
    "title", ["SECOND OPINION; A sample", "A MATTER OF OPINION", "ONE STRONG OPINION"]
)
def test_titles_that_only_hold_the_word_opinion_are_not_headings(title: str) -> None:
    assert not summaries.is_opinion_title(title)


@pytest.mark.parametrize(
    "section", ["Outlook", "PLUM-LINE", "Right-Turn", "kristof", "Post-Partisan"]
)
def test_opinion_sections_without_an_opinion_word(section: str) -> None:
    assert summaries.is_opinion_section(section)


def test_anonymous_is_not_an_author_in_the_tables() -> None:
    articles = make_articles({"author": "Anonymous"}, {"author": "Doe, Jane"}, {"author": None})
    assert tables.doc_type_table(articles)[1] == ["Commentary", "3", "33.3%"]
    assert tables.newspaper_table(articles)[-1][-1] == "33.3%"


@pytest.mark.parametrize("section", ["Currents", "CURRENTS & BOOKS", "Ideas"])
def test_opinion_sections_of_newsday(section: str) -> None:
    assert summaries.is_opinion_section(section)


@pytest.mark.parametrize(
    "title", ["opinion exchange: A sample", "LETTERS:  [NASSAU Edition ]", "Letters"]
)
def test_more_opinion_page_headings_in_titles(title: str) -> None:
    assert summaries.is_opinion_title(title)


def test_letters_to_another_desk_are_not_the_opinion_page() -> None:
    assert not summaries.is_opinion_title("LETTERS TO THE SPORTS EDITOR:  [FINAL Edition ]")


@pytest.mark.parametrize(
    "title",
    [
        "Punchlines",
        "PUNCHLINES: \xa0 [NASSAU AND SUFFOLK Edition ]",
        "Punchlines: Did anyone read the bill?",
        "IN OTHER WORDS: A sampling of opinions",
        "In Other Words A sampling of other opinions: \xa0 [Chicago Edition ]",
        "IN OTHER WORDS; A sam pling of opinions",
        "IN OTHER WORDS: A\xa0sampling of opinions",
        "Jane Doe and Richard Roe on the new move: Punchlines",
        "Late-night comics on the week in Washington: Punchline",
        "Did you play? Punchlines",
        "Best of Late Night: Comics say enough",
        "Politics and social media do not mix: Best of Late Night",
        "Jane Doe examines the week in Washington in Best of Late Night",
        "Jane Doe has an idea in Best of Late Night.",
        "EDITORIALS ELSEWHERE; Death and taxes: \xa0 [HOME EDITION ]",
    ],
)
def test_headings_of_compiled_pages_are_recognised(title: str) -> None:
    assert summaries.is_compiled_title(title)


@pytest.mark.parametrize(
    "title",
    [
        "The punchline that hid a murder",
        "These appointments are punchlines to a joke",
        "In Other Words, That's Life",
        "IN OTHER WORDS . . .",
        "A sample of opinion",
        "What is so funny? Nothing.: \xa0 Punchlines about punching are no joke",
        "LOCAL PUNCHLINES: COMEDIANS GIVE THEIR TWO CENTS",
        "The best of late night television is behind us",
        "Editorials elsewhere said the same",
        None,
    ],
)
def test_other_titles_are_not_compiled_pages(title: str | None) -> None:
    assert not summaries.is_compiled_title(title)


@pytest.mark.parametrize("title", ["PANEL DISCUSSION; War Baby", "Panel Discussion; x"])
def test_the_heading_of_a_page_of_cartoons_is_a_cartoon_label(title: str) -> None:
    assert summaries.is_cartoon_title(title)
    assert not summaries.is_cartoon_title("Panel discussion on trade was useful")
