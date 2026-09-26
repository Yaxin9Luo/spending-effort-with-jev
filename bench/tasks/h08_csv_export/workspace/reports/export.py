"""Export ticket records to CSV and read them back."""
from datetime import date, datetime
from decimal import Decimal

from .csvio import read_rows, write_rows


def format_value(value):
    """How a single value appears in the export.

    None -> "", booleans -> "true"/"false", datetimes/dates -> ISO 8601,
    floats -> two decimals, everything else -> str(value).
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def export_records(records, columns, delimiter=","):
    """CSV text with a header row of `columns`, then one row per record (a dict).

    Missing keys export as empty fields.
    """
    rows = [list(columns)]
    for rec in records:
        rows.append([format_value(rec.get(col)) for col in columns])
    return write_rows(rows, delimiter)


def import_records(text, delimiter=","):
    """Inverse of export_records: list of dicts (all values are strings)."""
    rows = read_rows(text, delimiter)
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    return [dict(zip(header, row)) for row in body]
