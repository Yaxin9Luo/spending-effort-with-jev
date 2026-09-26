import unittest

from tablekit.render import render_table


class RenderTest(unittest.TestCase):
    def test_render(self):
        out = render_table([{"a": "x", "b": "long"}], ["a", "b"])
        self.assertEqual(out, "a  b\n-  ----\nx  long")


if __name__ == "__main__":
    unittest.main()
