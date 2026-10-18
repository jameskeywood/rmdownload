"""Render rmc's SVG in a form svglib can reproduce faithfully.

rmc's exporter targets browsers; svglib mishandles two of its choices on the
way to PDF:

* it leaves ``stroke-linejoin`` at the SVG default (miter), so jitter in the
  raw point stream turns sharp direction changes into needle-like spikes;
* it applies transparency with the ``opacity`` property and writes colours as
  ``rgba(r, g, b, 255)``, neither of which svglib understands, so strokes that
  should be transparent or coloured come out opaque black.

This module swaps rmc's stroke renderer for one that emits round joins and
explicit ``stroke``/``stroke-opacity`` style values with the alpha folded in.
"""

import re

from rmc.exporters import svg as rmc_svg
from rmc.exporters.writing_tools import Pen, lookup_pen_color
from rmscene import scene_items as si

_COLOR_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")


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


def draw_stroke(item: si.Line, output) -> None:
    """Draw one stroke as polylines, without miter spikes or lost alpha."""
    pen = Pen.create(
        item.tool.value,
        lookup_pen_color(item.color.value, item.color_rgba),
        item.thickness_scale,
    )

    last_segment_width = segment_width = 0
    for point_id, point in enumerate(item.points):
        if point_id % pen.segment_length == 0:
            if point_id > 0:
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
            if point_id > 0:
                previous = item.points[point_id - 1]
                output.write(f'{rmc_svg.xx(previous.x):.3f},{rmc_svg.yy(previous.y):.3f} ')

        last_segment_width = segment_width
        output.write(f'{rmc_svg.xx(point.x):.3f},{rmc_svg.yy(point.y):.3f} ')

    output.write('" />\n')


# ``tree_to_svg`` looks ``draw_stroke`` up at call time, so the replacement
# applies to every stroke it draws.
rmc_svg.draw_stroke = draw_stroke


def tree_to_svg(tree, output) -> None:
    """rmc's ``tree_to_svg`` with svglib-compatible stroke rendering."""
    rmc_svg.tree_to_svg(tree, output)
