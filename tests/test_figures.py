"""Tests for econ_corpus.figures."""

from econ_corpus import figures

YEARS = [
    ["Year", "Records", "Unique ids", "With author"],
    ["2001", "1,200", "1,000", "50.0%"],
    ["2002", "500", "500", "40.0%"],
    ["Unknown year", "9", "9", "0.0%"],
]


def test_year_chart_is_an_svg_document() -> None:
    svg = figures.year_chart_svg(YEARS)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_year_chart_draws_two_bars_per_year_and_skips_unknown_year() -> None:
    svg = figures.year_chart_svg(YEARS)
    assert svg.count('class="bar') == 4
    assert "Unknown" not in svg


def test_year_chart_labels_the_years_and_has_a_title_and_legend() -> None:
    svg = figures.year_chart_svg(YEARS)
    assert "2001" in svg
    assert "2002" in svg
    assert "<title>" in svg
    assert "Records" in svg
    assert "Distinct ids" in svg


def test_taller_bar_for_larger_count() -> None:
    svg = figures.year_chart_svg(YEARS)
    heights = [
        float(h)
        for h in __import__("re").findall(r'class="bar records" [^>]*height="([\d.]+)"', svg)
    ]
    assert heights[0] > heights[1]
