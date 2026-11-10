"""The map of the pipeline for the overview datasheet, drawn as plain SVG.

Input: lanes, one per pipeline, each a row of boxes (a step of the pipeline or a dataset)
joined by arrows that carry a label (what passes, or what is left out).
Output: one SVG document as text.

Lives here: the drawing. Does not live here: which steps there are and their counts
(overview), or the other charts (figures).
"""

from typing import Literal, NamedTuple

from econ_corpus.shared.figures import COLOURS, TEXT

# The figure is printed at the width of a page, so the text must be large next to the width:
# at most five boxes per lane, with room for a label of two lines above each arrow.
BOXES = 5
BOX_W, BOX_H, GAP = 150, 66, 44  # a box, and the space between two boxes for the arrow
LEFT = 20
WIDTH = 2 * LEFT + BOXES * BOX_W + (BOXES - 1) * GAP
LANE_TOP, LANE_H, LANE_GAP = 56, 138, 24  # where the first lane starts, its height, the gap
LINE = 16  # height of a line of text
FONT, SMALL = 15, 12.5  # names and titles; roles and arrow labels
MONO = "monospace"


class Box(NamedTuple):
    """A step of the pipeline (a module, white) or a dataset (filled)."""

    name: str
    role: str  # one or two lines ('\n'): what the step does or how big the dataset is
    kind: Literal["step", "data"]


class Lane(NamedTuple):
    """One pipeline: its title, its boxes in order and the label of each arrow between them."""

    title: str
    boxes: list[Box]
    arrows: list[str]  # len(boxes) - 1 labels, each one or two lines; '' for a bare arrow


def height(n_lanes: int) -> int:
    """Return the height of a map with `n_lanes` lanes."""
    return LANE_TOP + n_lanes * LANE_H + (n_lanes - 1) * LANE_GAP + 10


def _lines(x: float, y: float, text: str, **attrs: str) -> str:
    """Draw a text of one or two lines, centred on x, the first line's baseline at y."""
    extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    spans = "".join(
        f'<tspan x="{x:.1f}" dy="{LINE if i else 0}">{line}</tspan>'
        for i, line in enumerate(text.split("\n"))
    )
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" {extra}>{spans}</text>'


def _box(x: float, y: float, box: Box) -> list[str]:
    fill, ink = (COLOURS[0], "#ffffff") if box.kind == "data" else ("#ffffff", TEXT)
    family = MONO if box.kind == "step" else "sans-serif"
    middle = x + BOX_W / 2
    name_y = y + 24 if "\n" in box.role else y + 30
    return [
        (
            f'<rect class="box {box.kind}" x="{x:.1f}" y="{y}" width="{BOX_W}" '
            f'height="{BOX_H}" rx="4" fill="{fill}" stroke="{COLOURS[0]}"/>'
        ),
        _lines(middle, name_y, box.name, fill=ink, font_weight="bold", font_family=family),
        _lines(middle, name_y + LINE + 2, box.role, fill=ink, font_size=str(SMALL)),
    ]


def _arrow(x: float, y: float, label: str, top: float) -> list[str]:
    """Draw an arrow from x to x + GAP at height y; its label sits above the boxes, at top."""
    tip = x + GAP
    parts = [
        f'<line class="arrow" x1="{x:.1f}" x2="{tip - 6:.1f}" y1="{y}" y2="{y}" stroke="{TEXT}"/>',
        (
            f'<path d="M{tip - 7:.1f},{y - 4} L{tip:.1f},{y} L{tip - 7:.1f},{y + 4} Z" '
            f'fill="{TEXT}"/>'
        ),
    ]
    if label:
        lines = label.count("\n") + 1
        parts.append(_lines(x + GAP / 2, top - LINE * (lines - 1), label, font_size=str(SMALL)))
    return parts


def pipeline_svg(lanes: list[Lane], *, heading: str) -> str:
    """Draw the lanes one under the other, each a row of boxes joined by labelled arrows.

    A lane holds at most BOXES boxes and one arrow label per pair of boxes.
    """
    for lane in lanes:
        if len(lane.boxes) > BOXES or len(lane.arrows) != len(lane.boxes) - 1:
            msg = f"lane {lane.title!r}: at most {BOXES} boxes, one arrow between each two"
            raise ValueError(msg)
    total = height(len(lanes))
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {total}" '
            f'font-family="sans-serif" font-size="{FONT}" fill="{TEXT}">'
        ),
        f"<title>{heading}</title>",
        f'<rect width="{WIDTH}" height="{total}" fill="#ffffff"/>',
        f'<text x="{LEFT}" y="26" font-size="{FONT + 2}">{heading}</text>',
    ]
    for n, lane in enumerate(lanes):
        top = LANE_TOP + n * (LANE_H + LANE_GAP)
        box_y = top + 2 * LINE + 28  # room for the title and a label of two lines
        parts.append(f'<text x="{LEFT}" y="{top + LINE}" font-weight="bold">{lane.title}</text>')
        for i, box in enumerate(lane.boxes):
            x = LEFT + i * (BOX_W + GAP)
            parts += _box(x, box_y, box)
            if i < len(lane.arrows):
                parts += _arrow(x + BOX_W, box_y + BOX_H / 2, lane.arrows[i], box_y - 8)
    return "\n".join([*parts, "</svg>"]) + "\n"
