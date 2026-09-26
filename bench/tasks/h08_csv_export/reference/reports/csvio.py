"""Our own small CSV reader/writer (the export format predates our use of the csv module)."""


def _quote(field, delimiter):
    if any(c in field for c in (delimiter, '"', "\r", "\n")):
        return '"' + field.replace('"', '""') + '"'
    return field


def write_rows(rows, delimiter=","):
    """Serialize rows (lists of strings) as CSV text, RFC 4180 style.

    Fields are separated by `delimiter` and every row ends with CRLF. A field
    is wrapped in double quotes if it contains the delimiter, a double quote,
    CR or LF; inside a quoted field each double quote is written twice. All
    other fields are written exactly as they are (no trimming). A row made of
    a single empty field is written as "" so that the row isn't lost.

    read_rows(write_rows(rows, d), d) == rows for any non-empty rows of strings.
    """
    out = []
    for row in rows:
        row = list(row)
        if row == [""]:
            out.append('""\r\n')
            continue
        out.append(delimiter.join(_quote(f, delimiter) for f in row) + "\r\n")
    return "".join(out)


def read_rows(text, delimiter=","):
    """Parse CSV text (as produced by write_rows, or any RFC 4180 file) into lists of strings.

    Quoted fields may contain the delimiter, doubled double quotes and line
    breaks. Unquoted fields are taken verbatim, including any spaces. Rows end
    with CRLF or a bare LF; the line ending after the last row is optional.
    Empty text gives [].
    """
    rows = []
    row, field = [], []
    i, n = 0, len(text)
    in_quotes = False
    at_field_start = True
    while i < n:
        c = text[i]
        if in_quotes:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                in_quotes = False
            else:
                field.append(c)
            i += 1
            continue
        if c == '"' and at_field_start:
            in_quotes = True
            at_field_start = False
            i += 1
            continue
        if c == delimiter:
            row.append("".join(field))
            field = []
            at_field_start = True
            i += 1
            continue
        if c == "\n" or (c == "\r" and i + 1 < n and text[i + 1] == "\n"):
            row.append("".join(field))
            rows.append(row)
            row, field = [], []
            at_field_start = True
            i += 2 if c == "\r" else 1
            continue
        field.append(c)
        at_field_start = False
        i += 1
    if in_quotes:
        raise ValueError("unterminated quoted field")
    if field or row or not at_field_start:
        row.append("".join(field))
        rows.append(row)
    return rows
