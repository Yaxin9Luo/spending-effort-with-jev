"""Markdown table formatting for our release-notes generator."""
import re

_ALIGNS = (None, "left", "right", "center")


def _cell(value):
    s = "" if value is None else str(value)
    s = s.strip()
    s = re.sub(r"\r\n|\r|\n", "<br>", s)
    return s.replace("|", "\\|")


def _pad(text, width, align):
    gap = width - len(text)
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def _sep(width, align):
    if align == "left":
        return ":" + "-" * (width - 1)
    if align == "right":
        return "-" * (width - 1) + ":"
    if align == "center":
        return ":" + "-" * (width - 2) + ":"
    return "-" * width


def format_table(headers, rows, align=None):
    headers = [_cell(h) for h in headers]
    ncol = len(headers)
    if ncol == 0:
        raise ValueError("headers must not be empty")
    if align is None:
        align = [None] * ncol
    align = list(align)
    if len(align) != ncol:
        raise ValueError("align must have one entry per column")
    for a in align:
        if a not in _ALIGNS:
            raise ValueError(f"unknown alignment {a!r}")
    body = []
    for row in rows:
        row = list(row)
        if len(row) > ncol:
            raise ValueError("row has more cells than headers")
        cells = [_cell(v) for v in row] + [""] * (ncol - len(row))
        body.append(cells)
    widths = [max([3, len(headers[i])] + [len(r[i]) for r in body]) for i in range(ncol)]

    def line(cells):
        return "| " + " | ".join(_pad(c, widths[i], align[i]) for i, c in enumerate(cells)) + " |"

    out = [line(headers), "| " + " | ".join(_sep(widths[i], align[i]) for i in range(ncol)) + " |"]
    out += [line(r) for r in body]
    return "\n".join(out)
