"""Render notebook strokes to SVG in a form svglib can reproduce faithfully.

rmc's exporter targets browsers, but its output goes through svglib here:

* it leaves ``stroke-linejoin`` at the SVG default (miter), so the jitter in
  the raw point stream turns every sharp direction change into a needle-like
  spike;
* it applies transparency with the ``opacity`` property, which svglib ignores;
* it writes colours as ``rgba(r, g, b, 255)``, which reportlab's colour parser
  rejects (the alpha must be between 0 and 1), so svglib silently falls back
  to the default black stroke.

This module swaps rmc's stroke renderer for one that emits round joins and
explicit ``stroke``/``stroke-opacity`` style values with the alpha folded in.
"""

import re

from rmc.exporters import svg as rmc_svg
from rmc.exporters.writing_tools import Pen, lookup_pen_color
from rmscene import scene_items as si

_COLOR_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")

# Neighbour weight of the 1-2-1 smoothing kernel; 0.25 is the standard
# kernel.  The tablet samples a lot of sensor jitter into the point stream;
# a single pass removes most of it without visibly rounding deliberate
# corners.  Set to 0.0 to disable smoothing.
SMOOTHING = 0.25


def svg_color(color: str, opacity: float) -> tuple[str, float]:
    """Split an ``rgb()``/``rgba()`` string into an opaque colour and alpha.

    Alpha (0-255 or 0-1) is folded into the given opacity so the result can be
    emitted with ``stroke`` and ``stroke-opacity``, which svglib understands.
    """
    match = _COLOR_RE.fullmatch(color)
    if match is None:
        return color, max(0.0, min(1.0, opacity))
    red, green, blue, alpha = match.groups()
    if alpha is not None:
        alpha = float(alpha)
        opacity *= alpha / 255 if alpha > 1 else alpha
    return f"rgb({red}, {green}, {blue})", max(0.0, min(1.0, opacity))


def smooth_points(points: list[si.Point]) -> list[tuple[float, float]]:
    """Return (x, y) coordinates with a single 1-2-1 smoothing pass applied."""
    coords = [(point.x, point.y) for point in points]
    if SMOOTHING <= 0 or len(coords) < 3:
        return coords
    inner = 1 - 2 * SMOOTHING
    smoothed = list(coords)
    for i in range(1, len(coords) - 1):
        x0, y0 = coords[i - 1]
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        smoothed[i] = (
            SMOOTHING * x0 + inner * x1 + SMOOTHING * x2,
            SMOOTHING * y0 + inner * y1 + SMOOTHING * y2,
        )
    return smoothed


def draw_stroke(item: si.Line, output) -> None:
    """Draw one stroke as polylines, without miter spikes or lost alpha."""
    pen = Pen.create(
        item.tool.value,
        lookup_pen_color(item.color.value, item.color_rgba),
        item.thickness_scale,
    )
    coords = smooth_points(item.points)

    last_xy = None
    last_segment_width = segment_width = 0
    for point_id, point in enumerate(item.points):
        if point_id % pen.segment_length == 0:
            if last_xy is not None:
                output.write('"/>\n')

            segment_color = pen.get_segment_color(
                point.speed, point.direction, point.width, point.pressure, last_segment_width
            )
            segment_width = pen.get_segment_width(
                point.speed, point.direction, point.width, point.pressure, last_segment_width
            )
            segment_opacity = pen.get_segment_opacity(
                point.speed, point.direction, point.width, point.pressure, last_segment_width
            )
            stroke, opacity = svg_color(segment_color, segment_opacity)

            output.write('\t\t\t<polyline ')
            output.write(f'style="fill:none; stroke:{stroke}; '
                         f'stroke-width:{rmc_svg.scale(segment_width):.3f}; stroke-opacity:{opacity:.3f}" ')
            output.write(f'stroke-linecap="{pen.stroke_linecap}" stroke-linejoin="round" ')
            output.write('points="')
            if last_xy is not None:
                x, y = coords[point_id - 1]
                output.write(f'{rmc_svg.xx(x):.3f},{rmc_svg.yy(y):.3f} ')

        last_segment_width = segment_width
        last_xy = coords[point_id]
        x, y = last_xy
        output.write(f'{rmc_svg.xx(x):.3f},{rmc_svg.yy(y):.3f} ')

    output.write('" />\n')


# ``tree_to_svg`` looks ``draw_stroke`` up at call time, so the replacement
# applies to the whole tree.
rmc_svg.draw_stroke = draw_stroke


def tree_to_svg(tree, output) -> None:
    """rmc's ``tree_to_svg`` with svglib-compatible stroke rendering."""
    rmc_svg.tree_to_svg(tree, output)
