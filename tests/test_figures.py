"""Tests for econ_corpus.shared.figures."""

from econ_corpus.shared import figures

PAIR = ("Records", "Distinct ids")
TITLE = "Records per year"
YEARS = [
    ["Year", "Records", "Unique ids", "With author"],
    ["2001", "1,200", "1,000", "50.0%"],
    ["2002", "500", "500", "40.0%"],
    ["Unknown year", "9", "9", "0.0%"],
]


def test_year_chart_is_an_svg_document() -> None:
    svg = figures.year_chart_svg(YEARS, labels=PAIR, heading=TITLE)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_year_chart_draws_two_bars_per_year_and_skips_unknown_year() -> None:
    svg = figures.year_chart_svg(YEARS, labels=PAIR, heading=TITLE)
    assert svg.count('class="bar') == 4
    assert "Unknown" not in svg


def test_year_chart_labels_the_years_and_has_a_title_and_legend() -> None:
    svg = figures.year_chart_svg(YEARS, labels=PAIR, heading=TITLE)
    assert "2001" in svg
    assert "2002" in svg
    assert "<title>" in svg
    assert "Records" in svg
    assert "Distinct ids" in svg


def test_taller_bar_for_larger_count() -> None:
    svg = figures.year_chart_svg(YEARS, labels=PAIR, heading=TITLE)
    heights = [
        float(h)
        for h in __import__("re").findall(r'class="bar records" [^>]*height="([\d.]+)"', svg)
    ]
    assert heights[0] > heights[1]


def test_one_series_draws_one_bar_per_year_and_no_second_legend_entry() -> None:
    svg = figures.year_chart_svg(YEARS, labels=("Records",), heading=TITLE)
    assert svg.count('class="bar') == 2
    assert "Records" in svg
    assert "Distinct ids" not in svg


def test_the_heading_is_the_title_and_the_caption_inside_the_chart() -> None:
    svg = figures.year_chart_svg(YEARS, labels=("Records",), heading="Shared table, by year")
    assert "<title>Shared table, by year</title>" in svg
    assert ">Shared table, by year</text>" in svg


def test_series_take_their_values_from_the_columns_in_order() -> None:
    rows = [["Year", "As parsed", "Shared table"], ["2014", "112,098", "39,087"]]
    svg = figures.year_chart_svg(rows, labels=("As parsed", "Shared table"), heading=TITLE)
    heights = [
        float(h)
        for h in __import__("re").findall(r'class="bar [^"]*" [^>]*height="([\d.]+)"', svg)
    ]
    assert svg.count('class="bar') == 2
    assert heights[0] > heights[1]
    assert "As parsed" in svg
    assert "Shared table" in svg


STEPS = [
    ("file_footer", "Row is a file footer", 2, 8, ""),
    ("duplicate_text", "Same text as an earlier record", 3, 5, "Shared raw table"),
    ("no_author", "Unsigned", 1, 4, "Cleaned dataset"),
]


def test_flow_chart_is_an_svg_with_a_box_for_the_start_and_each_step() -> None:
    svg = figures.flow_svg(STEPS, start=10, heading="From the exports to the cleaned dataset")
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert svg.count('class="remaining"') == 4
    assert svg.count('class="removed"') == 3


def test_flow_chart_shows_counts_reasons_and_table_names() -> None:
    svg = figures.flow_svg(STEPS, start=1234567, heading="From the exports to the cleaned dataset")
    assert "1,234,567" in svg
    assert "Row is a file footer" in svg
    assert "Shared raw table" in svg
    assert "Cleaned dataset" in svg
    assert "<title>From the exports to the cleaned dataset</title>" in svg
