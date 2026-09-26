import unittest

from mdtable import format_table


class TestFormat(unittest.TestCase):
    def test_spec_example(self):
        got = format_table(["Name", "Qty", "Note"], [["apple", 3, None], ["kiwi", 12, "a|b"]],
                           align=["left", "right", "center"])
        want = ("| Name  | Qty | Note |\n"
                "| :---- | --: | :--: |\n"
                "| apple |   3 |      |\n"
                "| kiwi  |  12 | a\\|b |")
        self.assertEqual(got, want)

    def test_no_align_default(self):
        got = format_table(["a", "bb"], [["x", "yyyy"]])
        want = ("| a   | bb   |\n"
                "| --- | ---- |\n"
                "| x   | yyyy |")
        self.assertEqual(got, want)

    def test_minimum_width_three(self):
        got = format_table(["x"], [["y"]], align=["center"])
        self.assertEqual(got, "|  x  |\n| :-: |\n|  y  |")

    def test_min_width_right(self):
        self.assertEqual(format_table(["n"], [[1]], align=["right"]), "|   n |\n| --: |\n|   1 |")

    def test_center_padding_split(self):
        got = format_table(["Title"], [["ab"], ["abc"], ["abcd"]], align=["center"])
        lines = got.split("\n")
        self.assertEqual(lines[1], "| :---: |")
        self.assertEqual(lines[2], "|  ab   |")   # gap 3 -> 1 left, 2 right
        self.assertEqual(lines[3], "|  abc  |")
        self.assertEqual(lines[4], "| abcd  |")   # gap 1 -> 0 left, 1 right

    def test_header_padded_with_column_alignment(self):
        got = format_table(["n"], [["12345"]], align=["right"])
        self.assertEqual(got.split("\n")[0], "|     n |")

    def test_mixed_none_align_entries(self):
        got = format_table(["a", "b"], [["1", "2"]], align=[None, "left"])
        self.assertEqual(got, "| a   | b   |\n| --- | :-- |\n| 1   | 2   |")

    def test_no_trailing_newline_and_line_count(self):
        got = format_table(["h"], [["1"], ["2"]])
        self.assertFalse(got.endswith("\n"))
        self.assertEqual(len(got.split("\n")), 4)

    def test_header_only(self):
        self.assertEqual(format_table(["Col", "X"], []), "| Col | X   |\n| --- | --- |")


class TestCells(unittest.TestCase):
    def test_none_and_numbers(self):
        got = format_table(["v", "w"], [[None, 1.5], [0, True]])
        self.assertEqual(got, "| v   | w    |\n| --- | ---- |\n|     | 1.5  |\n| 0   | True |")

    def test_whitespace_stripped(self):
        got = format_table(["  h  "], [["  pad  "]])
        self.assertEqual(got, "| h   |\n| --- |\n| pad |")

    def test_newlines(self):
        got = format_table(["t"], [["a\nb"], ["c\r\nd"], ["e\rf"]])
        lines = got.split("\n")
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[2], "| a<br>b |")
        self.assertEqual(lines[3], "| c<br>d |")
        self.assertEqual(lines[4], "| e<br>f |")

    def test_pipe_escape_counts_toward_width(self):
        got = format_table(["p"], [["a|b|c"]])
        self.assertEqual(got, "| p       |\n| ------- |\n| a\\|b\\|c |")

    def test_header_escaping(self):
        got = format_table(["a|b"], [])
        self.assertEqual(got, "| a\\|b |\n| ---- |")

    def test_short_row_padded(self):
        got = format_table(["a", "b", "c"], [["1"], ["1", "2"]])
        self.assertEqual(got, "| a   | b   | c   |\n| --- | --- | --- |\n| 1   |     |     |\n| 1   | 2   |     |")

    def test_generator_rows(self):
        rows = ((str(i), i * i) for i in range(1, 4))
        got = format_table(["n", "sq"], rows, align=[None, "right"])
        self.assertEqual(got, "| n   |  sq |\n| --- | --: |\n| 1   |   1 |\n| 2   |   4 |\n| 3   |   9 |")

    def test_tuple_rows(self):
        self.assertEqual(format_table(("a",), [("x",)]), "| a   |\n| --- |\n| x   |")


class TestErrors(unittest.TestCase):
    def test_long_row(self):
        with self.assertRaises(ValueError):
            format_table(["a"], [["1", "2"]])

    def test_empty_headers(self):
        with self.assertRaises(ValueError):
            format_table([], [])

    def test_align_wrong_length(self):
        with self.assertRaises(ValueError):
            format_table(["a", "b"], [], align=["left"])

    def test_unknown_align(self):
        with self.assertRaises(ValueError):
            format_table(["a"], [], align=["middle"])


if __name__ == "__main__":
    unittest.main()
