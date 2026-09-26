"""Hidden tests for h08_csv_export."""
import random
import unittest
from datetime import date, datetime
from decimal import Decimal

from reports.csvio import read_rows, write_rows
from reports.export import export_records, format_value, import_records


class TestWriter(unittest.TestCase):
    def test_quotes_are_doubled(self):
        self.assertEqual(write_rows([["1", 'He said "hi"']]), '1,"He said ""hi"""\r\n')
        self.assertEqual(write_rows([['"']]), '""""\r\n')

    def test_cr_lf_and_delimiter_trigger_quoting(self):
        self.assertEqual(write_rows([["a,b", "c\rd", "e\nf", "g\r\nh"]]),
                         '"a,b","c\rd","e\nf","g\r\nh"\r\n')

    def test_custom_delimiter_quoting(self):
        self.assertEqual(write_rows([["a;b", "c,d", "e"]], delimiter=";"), '"a;b";c,d;e\r\n')
        self.assertEqual(write_rows([["a\tb", "c,d"]], delimiter="\t"), '"a\tb"\tc,d\r\n')

    def test_plain_fields_verbatim(self):
        self.assertEqual(write_rows([["a", " b ", "", "x'y"]]), "a, b ,,x'y\r\n")

    def test_single_empty_field_row(self):
        self.assertEqual(write_rows([[""], ["a"]]), '""\r\na\r\n')

    def test_multiple_rows(self):
        self.assertEqual(write_rows([["a", "b"], ["c", "d"]]), "a,b\r\nc,d\r\n")


class TestReader(unittest.TestCase):
    def test_rfc_style_input(self):
        text = 'a,"b\r\nc",d\r\ne,f,g\r\n'
        self.assertEqual(read_rows(text), [["a", "b\r\nc", "d"], ["e", "f", "g"]])

    def test_doubled_quotes(self):
        self.assertEqual(read_rows('"He said ""hi""",x\r\n'), [['He said "hi"', "x"]])
        self.assertEqual(read_rows('""""\r\n'), [['"']])

    def test_lf_endings_and_no_final_newline(self):
        self.assertEqual(read_rows("a,b\nc,d"), [["a", "b"], ["c", "d"]])
        self.assertEqual(read_rows("a,b\r\nc,d"), [["a", "b"], ["c", "d"]])

    def test_mixed_line_endings(self):
        self.assertEqual(read_rows('a,"x\r\ny"\nb,c\n'), [["a", "x\r\ny"], ["b", "c"]])
        self.assertEqual(read_rows("a\nb\r\nc"), [["a"], ["b"], ["c"]])

    def test_spaces_preserved(self):
        self.assertEqual(read_rows(" a , b \r\n"), [[" a ", " b "]])

    def test_empty_fields(self):
        self.assertEqual(read_rows("a,,b,\r\n"), [["a", "", "b", ""]])
        self.assertEqual(read_rows('"",x\r\n'), [["", "x"]])
        self.assertEqual(read_rows('""\r\n'), [[""]])

    def test_empty_text(self):
        self.assertEqual(read_rows(""), [])

    def test_only_cr_lf_and_lf_end_rows(self):
        for ch in ("\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " "):
            with self.subTest(ch=repr(ch)):
                self.assertEqual(read_rows("a" + ch + "b,c\r\n"), [["a" + ch + "b", "c"]])

    def test_custom_delimiter(self):
        self.assertEqual(read_rows('"a;b";c,d\r\n', delimiter=";"), [["a;b", "c,d"]])

    def test_backslash_is_not_an_escape(self):
        self.assertEqual(read_rows('"a\\",b\r\n'), [["a\\", "b"]])


ALPHABET = ["a", "b", " ", ",", ";", "\t", "|", '"', "\r", "\n", "\r\n", "\\", " ", "\x0c", "é", ""]


class TestRoundTrip(unittest.TestCase):
    def test_reported_multiline_note(self):
        rows = [["1", "line one\nline two"], ["2", "x"]]
        self.assertEqual(read_rows(write_rows(rows)), rows)

    def test_random_round_trip(self):
        rng = random.Random(99)
        for delimiter in (",", ";", "\t", "|"):
            for _ in range(300):
                rows = [["".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 6)))
                         for _ in range(rng.randint(1, 4))]
                        for _ in range(rng.randint(1, 4))]
                with self.subTest(delimiter=delimiter, rows=rows):
                    self.assertEqual(read_rows(write_rows(rows, delimiter), delimiter), rows)


class TestExport(unittest.TestCase):
    def test_export_regression(self):
        recs = [{"id": 1, "open": True, "note": "ok"}, {"id": 2, "open": False}]
        self.assertEqual(export_records(recs, ["id", "open", "note"]),
                         "id,open,note\r\n1,true,ok\r\n2,false,\r\n")

    def test_export_import_awkward_notes(self):
        recs = [{"id": 1, "note": 'said "no", then\r\nleft'},
                {"id": 2, "note": "  padded  "},
                {"id": 3, "note": None}]
        text = export_records(recs, ["id", "note"])
        self.assertEqual(import_records(text), [
            {"id": "1", "note": 'said "no", then\r\nleft'},
            {"id": "2", "note": "  padded  "},
            {"id": "3", "note": ""}])

    def test_export_semicolon(self):
        text = export_records([{"a": "x;y", "b": 1.5}], ["a", "b"], delimiter=";")
        self.assertEqual(text, 'a;b\r\n"x;y";1.50\r\n')
        self.assertEqual(import_records(text, delimiter=";"), [{"a": "x;y", "b": "1.50"}])

    def test_format_value_regression(self):
        self.assertEqual(format_value(None), "")
        self.assertEqual(format_value(False), "false")
        self.assertEqual(format_value(3), "3")
        self.assertEqual(format_value(2.5), "2.50")
        self.assertEqual(format_value(Decimal("1.10")), "1.10")
        self.assertEqual(format_value(datetime(2025, 1, 2, 3, 4, 5)), "2025-01-02T03:04:05")
        self.assertEqual(format_value(date(2025, 1, 2)), "2025-01-02")

    def test_import_empty(self):
        self.assertEqual(import_records(""), [])


if __name__ == "__main__":
    unittest.main()
