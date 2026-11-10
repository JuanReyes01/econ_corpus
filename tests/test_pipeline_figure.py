"""Tests for econ_corpus.shared.pipeline_figure on a made-up pipeline."""

import pytest

from econ_corpus.shared import pipeline_figure
from econ_corpus.shared.figures import MINUS
from econ_corpus.shared.pipeline_figure import Box, Lane

LANES = [
    Lane(
        "Pipeline 1: exports to the raw table",
        [
            Box("ProQuest exports", "3 files", "data"),
            Box("parse", "one row\nper record", "step"),
            Box("Raw table", "7 records", "data"),
        ],
        ["", f"{MINUS} 2 footers"],
    ),
    Lane(
        "Pipeline 2: raw table to the cleaned dataset",
        [Box("Raw table", "7 records", "data"), Box("processed", "three tables", "step")],
        [f"{MINUS} 4 unsigned"],
    ),
]


def test_the_map_is_an_svg_with_a_box_per_step_and_dataset() -> None:
    svg = pipeline_figure.pipeline_svg(LANES, heading="The pipeline")
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert svg.count('class="box step"') == 2
    assert svg.count('class="box data"') == 3
    assert "<title>The pipeline</title>" in svg


def test_the_map_shows_names_roles_lane_titles_and_arrow_labels() -> None:
    svg = pipeline_figure.pipeline_svg(LANES, heading="The pipeline")
    labels = (f"{MINUS} 2 footers", f"{MINUS} 4 unsigned")
    for text in ("parse", "processed", "3 files", "three tables", *labels):
        assert text in svg
    assert "Pipeline 1: exports to the raw table" in svg
    assert "Pipeline 2: raw table to the cleaned dataset" in svg


def test_a_role_of_two_lines_is_drawn_as_two_lines() -> None:
    svg = pipeline_figure.pipeline_svg(LANES, heading="The pipeline")
    assert "<tspan" in svg
    assert ">one row<" in svg
    assert ">per record<" in svg
    assert "one row\nper record" not in svg


def test_an_arrow_joins_each_pair_of_boxes_in_a_lane() -> None:
    svg = pipeline_figure.pipeline_svg(LANES, heading="The pipeline")
    assert svg.count('class="arrow"') == 3  # two in the first lane, one in the second


def test_a_label_sits_above_the_boxes_not_on_them() -> None:
    svg = pipeline_figure.pipeline_svg(LANES[:1], heading="The pipeline")
    box_top = float(__import__("re").search(r'class="box data" x="[\d.]+" y="([\d.]+)"', svg)[1])
    label = __import__("re").search(
        r'<text x="[\d.]+" y="([\d.]+)"[^>]*>(<tspan[^>]*>)?\u2212 2', svg
    )
    assert label is not None
    assert float(label[1]) < box_top


def test_a_lane_with_too_many_boxes_or_the_wrong_arrows_is_refused() -> None:
    boxes = [Box(f"step{i}", "role", "step") for i in range(pipeline_figure.BOXES + 1)]
    too_many = Lane("Too many", boxes, [""] * pipeline_figure.BOXES)
    with pytest.raises(ValueError, match="at most"):
        pipeline_figure.pipeline_svg([too_many], heading="x")
    wrong_arrows = Lane("Wrong arrows", boxes[:2], [])
    with pytest.raises(ValueError, match="one arrow"):
        pipeline_figure.pipeline_svg([wrong_arrows], heading="x")


def test_the_height_grows_with_the_lanes() -> None:
    one = pipeline_figure.pipeline_svg(LANES[:1], heading="The pipeline")
    two = pipeline_figure.pipeline_svg(LANES, heading="The pipeline")
    assert pipeline_figure.height(1) < pipeline_figure.height(2)
    assert f'viewBox="0 0 {pipeline_figure.WIDTH} {pipeline_figure.height(1)}"' in one
    assert f'viewBox="0 0 {pipeline_figure.WIDTH} {pipeline_figure.height(2)}"' in two
