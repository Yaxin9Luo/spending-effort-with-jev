import inspect
import typing
import unittest

import numtools.stats as stats

PUBLIC = ["mean", "median", "stdev", "clamp", "normalize", "word_lengths"]


class DocsAndHintsTest(unittest.TestCase):
    def test_docstrings(self):
        for name in PUBLIC:
            doc = inspect.getdoc(getattr(stats, name))
            self.assertTrue(doc and doc.strip(), f"{name} has no docstring")

    def test_all_params_and_return_annotated(self):
        for name in PUBLIC:
            fn = getattr(stats, name)
            sig = inspect.signature(fn)
            for p in sig.parameters.values():
                self.assertIsNot(p.annotation, inspect.Parameter.empty, f"{name}({p.name}) not annotated")
            self.assertIsNot(sig.return_annotation, inspect.Signature.empty, f"{name} return not annotated")

    def test_hints_resolve(self):
        for name in PUBLIC:
            hints = typing.get_type_hints(getattr(stats, name))
            self.assertIn("return", hints, name)

    def test_word_lengths_hints(self):
        hints = typing.get_type_hints(stats.word_lengths)
        self.assertIs(hints["text"], str)
        ret = hints["return"]
        self.assertIn(typing.get_origin(ret), (list,), ret)
        self.assertEqual(typing.get_args(ret), (int,))


class BehaviourTest(unittest.TestCase):
    def test_mean_median(self):
        self.assertEqual(stats.mean([1, 2, 3, 4]), 2.5)
        self.assertEqual(stats.median([3, 1, 2]), 2.0)
        self.assertEqual(stats.median([4, 1, 3, 2]), 2.5)
        with self.assertRaisesRegex(ValueError, r"mean\(\) of empty sequence"):
            stats.mean([])
        with self.assertRaisesRegex(ValueError, r"median\(\) of empty sequence"):
            stats.median([])

    def test_stdev(self):
        self.assertAlmostEqual(stats.stdev([2, 4, 4, 4, 5, 5, 7, 9]), 2.138089935299395)
        self.assertAlmostEqual(stats.stdev([2, 4, 4, 4, 5, 5, 7, 9], sample=False), 2.0)
        with self.assertRaises(ValueError):
            stats.stdev([1.0])

    def test_clamp(self):
        self.assertEqual(stats.clamp(5, 0, 3), 3)
        self.assertEqual(stats.clamp(-1, 0, 3), 0)
        self.assertEqual(stats.clamp(1.5, 0, 3), 1.5)
        with self.assertRaises(ValueError):
            stats.clamp(1, 3, 0)

    def test_normalize(self):
        self.assertEqual(stats.normalize([1, 1, 2]), [0.25, 0.25, 0.5])
        self.assertEqual(stats.normalize([0, 0]), [0.0, 0.0])
        self.assertEqual(stats.normalize([]), [])

    def test_word_lengths(self):
        self.assertEqual(stats.word_lengths("  the quick\tbrown\nfox "), [3, 5, 5, 3])
        self.assertEqual(stats.word_lengths(""), [])

    def test_private_helper_untouched(self):
        with self.assertRaisesRegex(ValueError, r"x\(\) of empty sequence"):
            stats._require_values([], "x")


if __name__ == "__main__":
    unittest.main()
