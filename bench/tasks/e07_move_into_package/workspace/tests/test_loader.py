import os
import unittest

import loader

HERE = os.path.dirname(os.path.abspath(__file__))


class LoaderTest(unittest.TestCase):
    def test_load_sample(self):
        rows = loader.load_records(os.path.join(HERE, "..", "data", "sample.csv"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"name": "Ada", "team": "core", "score": "91"})


if __name__ == "__main__":
    unittest.main()
