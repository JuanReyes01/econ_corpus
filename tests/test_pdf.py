"""Tests for econ_corpus.pdf (the HTML page only; the browser is not run)."""

from pathlib import Path

from econ_corpus import pdf

DOCS = Path("/srv/docs")


def test_page_renders_tables_and_headings() -> None:
    page = pdf.page("# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", DOCS)
    assert "<h1>Title</h1>" in page
    assert "<table>" in page
    assert "<td>2</td>" in page


def test_page_resolves_relative_figures_from_the_folder_of_the_document() -> None:
    page = pdf.page("![x](../reports/figures/a.svg)", DOCS)
    assert "<base href='file:///srv/docs/'>" in page
    assert page.startswith("<!doctype html>")
