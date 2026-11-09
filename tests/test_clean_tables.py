"""Tests for econ_corpus.clean_tables on tiny synthetic inputs."""

from econ_corpus import clean_tables

REASONS = ["kept", "kept", "file_footer", "no_author", "duplicate_id", "not_opinion", "kept"]


def test_flow_starts_with_the_rows_that_leave_the_raw_table() -> None:
    steps = clean_tables.flow(REASONS)
    assert [s.code for s in steps[:3]] == ["file_footer", "duplicate_id", "duplicate_text"]
    assert steps[-1].code == "no_person_author"
    assert "kept" not in [s.code for s in steps]


def test_flow_counts_what_each_step_removes_and_what_remains() -> None:
    steps = {s.code: s for s in clean_tables.flow(REASONS)}
    assert (steps["file_footer"].removed, steps["file_footer"].remaining) == (1, 6)
    assert (steps["duplicate_id"].removed, steps["duplicate_id"].remaining) == (1, 5)
    assert (steps["duplicate_text"].removed, steps["duplicate_text"].remaining) == (0, 5)
    assert (steps["not_opinion"].removed, steps["not_opinion"].remaining) == (1, 4)
    assert (steps["no_person_author"].removed, steps["no_person_author"].remaining) == (0, 3)


def test_flow_names_the_two_tables_it_passes_through() -> None:
    steps = {s.code: s for s in clean_tables.flow(REASONS)}
    assert steps["duplicate_text"].reached == "Shared raw table"
    assert steps["no_person_author"].reached == "Cleaned dataset"
    assert steps["not_opinion"].reached == ""


def test_flow_table_lists_every_step_under_the_parsed_total() -> None:
    table = clean_tables.flow_table(clean_tables.flow(REASONS))
    assert table[0] == ["Step", "Left out", "Records", "Remaining"]
    assert table[1] == ["Rows parsed", "", "", "7"]
    assert table[2][0] == "file_footer"
    assert table[2][2:] == ["1", "6"]
    assert table[-1][2:] == ["0", "3"]


def test_counts_table_orders_by_count_and_gives_shares() -> None:
    table = clean_tables.counts_table(["a", "b", "a", "a"], "Value")
    assert table == [["Value", "Count", "Share"], ["a", "3", "75.0%"], ["b", "1", "25.0%"]]


def test_binned_table_groups_numbers_into_named_ranges() -> None:
    bins = [("1", 1, 1), ("2 to 9", 2, 9), ("10 or more", 10, None)]
    table = clean_tables.binned_table([1, 1, 3, 9, 10, 250], bins, "Articles", "Authors")
    assert table == [
        ["Articles", "Authors", "Share"],
        ["1", "2", "33.3%"],
        ["2 to 9", "2", "33.3%"],
        ["10 or more", "2", "33.3%"],
    ]


def test_newspaper_table_counts_articles_by_edition_with_a_total() -> None:
    papers = ["Example Daily", "Example Daily", "Sample Times"]
    editions = ["print", "online", "pre-1997"]
    assert clean_tables.newspaper_table(papers, editions) == [
        ["Newspaper", "Articles", "Print", "Online", "Pre-1997", "Share"],
        ["Example Daily", "2", "1", "1", "0", "66.7%"],
        ["Sample Times", "1", "0", "0", "1", "33.3%"],
        ["Total", "3", "1", "1", "1", "100.0%"],
    ]


def test_decade_table_counts_articles_per_decade() -> None:
    assert clean_tables.decade_table([1985, 1989, 2001, None]) == [
        ["Decade", "Articles", "Share"],
        ["1980s", "2", "50.0%"],
        ["2000s", "1", "25.0%"],
        ["Unknown year", "1", "25.0%"],
    ]
