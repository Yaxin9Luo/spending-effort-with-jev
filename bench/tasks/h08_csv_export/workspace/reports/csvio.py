"""Our own small CSV reader/writer (the export format predates our use of the csv module)."""


def _quote(field, delimiter):
    if any(c in field for c in (",", '"', "\n")):
        return '"' + field.replace('"', '\\"') + '"'
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
    for line in text.splitlines():
        fields, cur, in_quotes = [], "", False
        i = 0
        while i < len(line):
            c = line[i]
            if in_quotes:
                if c == "\\" and i + 1 < len(line):
                    cur += line[i + 1]
                    i += 2
                    continue
                if c == '"':
                    in_quotes = False
                else:
                    cur += c
            elif c == '"':
                in_quotes = True
            elif c == delimiter:
                fields.append(cur.strip())
                cur = ""
            else:
                cur += c
            i += 1
        fields.append(cur.strip())
        rows.append(fields)
    return rows
