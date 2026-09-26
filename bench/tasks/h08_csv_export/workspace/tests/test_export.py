import unittest
from datetime import date

from reports.csvio import read_rows, write_rows
from reports.export import export_records, format_value, import_records


class TestCsv(unittest.TestCase):
    def test_write_plain(self):
        self.assertEqual(write_rows([["a", "b"], ["1", "2"]]), "a,b\r\n1,2\r\n")

    def test_write_comma(self):
        self.assertEqual(write_rows([["x,y", "z"]]), '"x,y",z\r\n')

    def test_read_plain(self):
        self.assertEqual(read_rows("a,b\r\n1,2\r\n"), [["a", "b"], ["1", "2"]])

    def test_read_quoted_comma(self):
        self.assertEqual(read_rows('"x,y",z\r\n'), [["x,y", "z"]])

    def test_round_trip_simple(self):
        rows = [["id", "note"], ["1", "hello, world"], ["2", "plain"]]
        self.assertEqual(read_rows(write_rows(rows)), rows)


class TestExport(unittest.TestCase):
    def test_format_value(self):
        self.assertEqual(format_value(None), "")
        self.assertEqual(format_value(True), "true")
        self.assertEqual(format_value(2.5), "2.50")
        self.assertEqual(format_value(date(2025, 1, 2)), "2025-01-02")

    def test_export(self):
        recs = [{"id": 1, "open": True, "note": "ok"}, {"id": 2, "open": False}]
        self.assertEqual(export_records(recs, ["id", "open", "note"]),
                         "id,open,note\r\n1,true,ok\r\n2,false,\r\n")

    def test_import(self):
        text = "id,note\r\n1,hi\r\n"
        self.assertEqual(import_records(text), [{"id": "1", "note": "hi"}])


if __name__ == "__main__":
    unittest.main()
