"""Figures for the datasheet, drawn as plain SVG so no plotting library is needed.

Input: tables as built by `tables` (list of string rows, header first).
Output: SVG documents as text, ready to be written next to the datasheet.

Lives here: pure functions that turn a table into a chart. Does not live here: the choice of
which tables to plot or where files go (datasheet).
"""

import math

from econ_corpus.tables import Table

WIDTH, HEIGHT = 900, 380
LEFT, RIGHT, TOP, BOTTOM = 70, 20, 50, 45
COLOURS = ("#4c78a8", "#f58518")  # colour-blind-safe blue and orange
TEXT = "#333333"
TICKS = 4  # intervals on the y axis
LABEL_EVERY = 5  # label every fifth year once there are many bars
MANY_BARS = 12
LEGEND_STEP = 115  # horizontal space per legend entry


def _to_int(cell: str) -> int:
    return int(cell.replace(",", ""))


def _nice_max(value: int) -> int:
    """Round up to 1, 2 or 5 times a power of ten, so the axis ticks are round numbers."""
    magnitude = 10 ** math.floor(math.log10(max(value, 1)))
    return next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= value)


def year_chart_svg(rows: Table, *, labels: tuple[str, ...], heading: str) -> str:
    """Draw one bar per series and publication year, side by side.

    Series k takes its values from column k + 1 of `rows` (Year, first series, second series,
    ...); rows whose first cell is not a year are skipped. All bars share one scale.
    """
    n = len(labels)
    data = [(r[0], [_to_int(r[k + 1]) for k in range(n)]) for r in rows[1:] if r[0].isdigit()]
    top = _nice_max(max(max(values) for _, values in data))
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    slot = plot_w / len(data)
    bar = slot * 0.8 / n
    base = TOP + plot_h
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'font-family="sans-serif" font-size="12" fill="{TEXT}">'
        ),
        f"<title>{heading}</title>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{LEFT}" y="22" font-size="14">{heading}</text>',
    ]
    for tick in range(TICKS + 1):
        value, y = top * tick / TICKS, base - plot_h * tick / TICKS
        parts += [
            f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="#dddddd"/>',
            f'<text x="{LEFT - 6}" y="{y + 4:.1f}" text-anchor="end">{value:,.0f}</text>',
        ]
    for i, (year, values) in enumerate(data):
        x = LEFT + i * slot + slot * 0.1
        for k, count in enumerate(values):
            h = plot_h * count / top
            kind = labels[k].casefold().replace(" ", "-")
            parts.append(
                f'<rect class="bar {kind}" x="{x + k * bar:.1f}" y="{base - h:.1f}" '
                f'width="{bar:.1f}" height="{h:.1f}" fill="{COLOURS[k]}"/>'
            )
        if len(data) <= MANY_BARS or int(year) % LABEL_EVERY == 0:
            middle = x + bar * n / 2
            parts.append(
                f'<text x="{middle:.1f}" y="{base + 16}" text-anchor="middle">{year}</text>'
            )
    for j, label in enumerate(labels):
        x = WIDTH - RIGHT - LEGEND_STEP * (n - j)
        parts += [
            f'<rect x="{x}" y="10" width="12" height="12" fill="{COLOURS[j]}"/>',
            f'<text x="{x + 16}" y="21">{label}</text>',
        ]
    return "\n".join([*parts, "</svg>"]) + "\n"
