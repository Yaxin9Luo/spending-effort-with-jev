import csv


def load_records(path):
    """Read a CSV file into a list of dicts, stripping whitespace from values."""
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]
