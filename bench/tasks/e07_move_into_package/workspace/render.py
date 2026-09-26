def render_table(records, columns):
    """Render records as a plain-text table with left-aligned columns."""
    widths = [max([len(c)] + [len(str(r.get(c, ""))) for r in records]) for c in columns]
    lines = ["  ".join(c.ljust(w) for c, w in zip(columns, widths)).rstrip()]
    lines.append("  ".join("-" * w for w in widths))
    for r in records:
        lines.append("  ".join(str(r.get(c, "")).ljust(w) for c, w in zip(columns, widths)).rstrip())
    return "\n".join(lines)
