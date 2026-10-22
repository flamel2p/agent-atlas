"""Serialize one computed result and draw its host-selected chart.

SVG rendering projects existing values onto coordinates. It never aggregates
records or calculates statistics. Null months end a line segment, so a chart
cannot silently imply interpolation. Labels pass through XML escaping before
entering either text or attributes; no label supplies markup or a file path.
"""

import json
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from html import escape

from .domain import Chart, Outcome, to_wire


def outcome_json(outcome: Outcome) -> str:
    return json.dumps(to_wire(outcome), ensure_ascii=True, allow_nan=False, indent=2) + "\n"


def _number(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.001")), "f")


def _text(x: int | str, y: int | str, text: str, extra: str = "") -> str:
    return f'<text x="{x}" y="{y}" {extra}>{escape(text)}</text>'


def render_svg(chart: Chart) -> str:
    """Return standalone SVG with exact values in labels and data attributes.

    Coordinate rounding affects drawing positions only. Numeric labels retain
    the exact formatted strings already present in the JSON report.
    """
    with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
        if chart.kind == "bar":
            height = 120 + 42 * len(chart.data)
        elif chart.kind == "table":
            height = 120 + 34 * len(chart.data)
        else:
            height = 430
        elements = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{height}" viewBox="0 0 1100 {height}" role="img" aria-label="{escape(chart.title, quote=True)}">',
            f"<title>{escape(chart.title)}</title>",
            '<rect width="100%" height="100%" fill="white"/>',
            '<g font-family="sans-serif" font-size="14" fill="#183047">',
            _text(20, 30, chart.title, 'font-size="18" font-weight="bold"'),
        ]
        match chart.kind:
            case "bar":
                baseline, extent = Decimal(390), Decimal(470)
                maximum = max(item.value for item in chart.data)
                scale = maximum if maximum > 0 else Decimal(1)
                elements.append(f'<line data-role="zero-baseline" x1="390" y1="60" x2="390" y2="{height - 50}" stroke="#5c6773"/>')
                elements.append(_text(390, 53, "0"))
                for index, item in enumerate(chart.data):
                    y = 68 + 42 * index
                    width = item.value / scale * extent
                    # A 40-character label must fit even when every glyph is W.
                    # Explicit text lengths keep the bounded label column fixed.
                    elements.extend((
                        _text(20, y + 18, item.label, f'font-family="monospace" textLength="{len(item.label) * 8}" lengthAdjust="spacingAndGlyphs"'),
                        f'<rect x="390" y="{y}" width="{_number(width)}" height="26" fill="#267c93" data-label="{escape(item.label, quote=True)}" data-value="{item.value}"/>',
                        _text(_number(baseline + width + 10), y + 18, str(item.value)),
                    ))
                elements.append(_text(20, height - 16, f"{chart.y_label}. Zero baseline; observed product subtotals."))
            case "line":
                observed = [item.value for item in chart.data if item.value is not None]
                maximum = max(observed)
                scale = maximum if maximum > 0 else Decimal(1)
                elements.extend((
                    '<path d="M 190 75 V 310 H 1010" fill="none" stroke="#5c6773"/>',
                    _text(180, 80, str(maximum), f'text-anchor="end" font-family="monospace" textLength="{len(str(maximum)) * 8}" lengthAdjust="spacingAndGlyphs"'),
                    _text(180, 315, "0", 'text-anchor="end"'),
                ))
                segments: list[list[str]] = [[]]
                marks: list[str] = []
                for index, item in enumerate(chart.data):
                    x = Decimal(190) + Decimal(index) * 820 / (len(chart.data) - 1)
                    elements.append(_text(_number(x), 340, item.label, 'text-anchor="middle"'))
                    if item.value is None:
                        segments.append([])
                        marks.append(_text(_number(x), 365, "no data", 'text-anchor="middle" fill="#596773"'))
                        continue
                    y = Decimal(310) - item.value / scale * 230
                    segments[-1].append(f"{_number(x)},{_number(y)}")
                    marks.append(
                        f'<circle cx="{_number(x)}" cy="{_number(y)}" r="5" fill="#267c93" data-label="{escape(item.label, quote=True)}" data-value="{item.value}">'
                        f'<title>{escape(item.label)}: {item.value} {escape(chart.y_label)}</title></circle>'
                    )
                for segment in segments:
                    if len(segment) >= 2:
                        elements.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="#267c93" stroke-width="2"/>')
                elements.extend(marks)
                elements.append(_text(20, 405, f"{chart.y_label}. Point titles contain exact values. Null months remain gaps; no interpolation is inferred."))
            case "table":
                elements.extend((_text(20, 65, chart.x_label, 'font-weight="bold"'), _text(480, 65, chart.y_label, 'font-weight="bold"')))
                for index, item in enumerate(chart.data):
                    y = 96 + 34 * index
                    value = str(item.value) if item.value is not None else chart.null_label
                    elements.extend((
                        f'<g data-label="{escape(item.label, quote=True)}" data-value="{item.value if item.value is not None else "null"}">',
                        _text(20, y, item.label), _text(480, y, value), "</g>",
                    ))
                elements.append(_text(20, height - 12, "Observed records only. Blank cells are excluded and disclosed in the report."))
        elements.extend(("</g>", "</svg>"))
        return "\n".join(elements) + "\n"
