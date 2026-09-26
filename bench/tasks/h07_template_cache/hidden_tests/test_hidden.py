"""Hidden tests for h07_template_cache."""
import unittest

from sitegen import Renderer, TemplateError, TemplateNotFound, TemplateStore


def make(templates):
    store = TemplateStore(templates)
    return store, Renderer(store)


class TestTransitiveInvalidation(unittest.TestCase):
    def test_footer_through_layout(self):
        store, r = make({
            "footer": "F1",
            "layout": '[{% include "footer" %}]',
            "page": '<{% include "layout" %}>',
        })
        self.assertEqual(r.render("page"), "<[F1]>")
        store.set("footer", "F2")
        self.assertEqual(r.render("page"), "<[F2]>")
        self.assertEqual(r.render("layout"), "[F2]")

    def test_four_level_chain(self):
        store, r = make({"d": "d1", "c": 'c{% include "d" %}', "b": 'b{% include "c" %}',
                         "a": 'a{% include "b" %}'})
        self.assertEqual(r.render("a"), "abcd1")
        store.set("d", "d2")
        self.assertEqual(r.render("a"), "abcd2")

    def test_two_pages_sharing_layout(self):
        store, r = make({"footer": "F1", "layout": 'L{% include "footer" %}',
                         "home": 'H{% include "layout" %}', "about": 'A{% include "layout" %}'})
        self.assertEqual((r.render("home"), r.render("about")), ("HLF1", "ALF1"))
        store.set("footer", "F2")
        self.assertEqual((r.render("home"), r.render("about")), ("HLF2", "ALF2"))

    def test_delete_nested_partial(self):
        store, r = make({"footer": "F", "layout": 'L{% include "footer" %}',
                         "page": 'P{% include "layout" %}'})
        self.assertEqual(r.render("page"), "PLF")
        store.delete("footer")
        with self.assertRaises(TemplateNotFound):
            r.render("page")
        store.set("footer", "G")
        self.assertEqual(r.render("page"), "PLG")

    def test_variables_in_nested_partial(self):
        store, r = make({"footer": "{{ year }}", "layout": '{% include "footer" %}',
                         "page": '{{ title }}/{% include "layout" %}'})
        self.assertEqual(r.render("page", {"title": "T", "year": 1}), "T/1")
        store.set("footer", "y={{ year }}")
        self.assertEqual(r.render("page", {"title": "T", "year": 2}), "T/y=2")


class TestCacheEfficiency(unittest.TestCase):
    def test_diamond_recompiles_each_affected_template_once(self):
        store, r = make({"footer": "F1", "a": 'a{% include "footer" %}',
                         "b": 'b{% include "footer" %}',
                         "page": '{% include "a" %}|{% include "b" %}'})
        self.assertEqual(r.render("page"), "aF1|bF1")
        n = r.compile_count
        store.set("footer", "F2")
        self.assertEqual(r.render("page"), "aF2|bF2")
        self.assertEqual(r.compile_count - n, 4)

    def test_unrelated_templates_stay_cached(self):
        store, r = make({"footer": "F", "layout": 'L{% include "footer" %}',
                         "page": 'P{% include "layout" %}', "other": "O", "sidebar": "S",
                         "blog": 'B{% include "sidebar" %}'})
        for name in ("page", "other", "blog"):
            r.render(name)
        n = r.compile_count
        store.set("footer", "F2")
        r.render("other")
        r.render("blog")
        self.assertEqual(r.compile_count, n)
        r.render("page")
        self.assertEqual(r.compile_count, n + 3)

    def test_removed_include_no_longer_tracked(self):
        store, r = make({"footer": "F", "page": 'P{% include "footer" %}'})
        r.render("page")
        store.set("page", "P-only")
        self.assertEqual(r.render("page"), "P-only")
        n = r.compile_count
        store.set("footer", "F2")
        self.assertEqual(r.render("page"), "P-only")
        self.assertEqual(r.compile_count, n)

    def test_added_include_is_tracked(self):
        store, r = make({"footer": "F", "page": "P"})
        self.assertEqual(r.render("page"), "P")
        store.set("page", 'P{% include "layout" %}')
        store.set("layout", 'L{% include "footer" %}')
        self.assertEqual(r.render("page"), "PLF")
        store.set("footer", "G")
        self.assertEqual(r.render("page"), "PLG")


class TestCycles(unittest.TestCase):
    def test_self_include(self):
        store, r = make({"a": 'x{% include "a" %}'})
        with self.assertRaises(TemplateError):
            r.render("a")

    def test_cycle_then_fixed(self):
        store, r = make({"a": 'A{% include "b" %}', "b": 'B{% include "a" %}'})
        with self.assertRaises(TemplateError):
            r.render("a")
        store.set("b", "B")
        self.assertEqual(r.render("a"), "AB")
        store.set("b", "B2")
        self.assertEqual(r.render("a"), "AB2")

    def test_long_cycle_then_fixed(self):
        store, r = make({"a": 'a{% include "b" %}', "b": 'b{% include "c" %}',
                         "c": 'c{% include "a" %}', "top": 'T{% include "a" %}'})
        with self.assertRaises(TemplateError):
            r.render("top")
        store.set("c", "c")
        self.assertEqual(r.render("top"), "Tabc")
        store.set("c", "C")
        self.assertEqual(r.render("top"), "TabC")


class TestMissing(unittest.TestCase):
    def test_include_created_later(self):
        store, r = make({"page": 'P{% include "layout" %}', "layout": 'L{% include "footer" %}'})
        with self.assertRaises(TemplateNotFound):
            r.render("page")
        store.set("footer", "F")
        self.assertEqual(r.render("page"), "PLF")
        store.set("footer", "G")
        self.assertEqual(r.render("page"), "PLG")

    def test_not_found_is_template_error(self):
        store, r = make({})
        with self.assertRaises(TemplateError):
            r.render("nope")


class TestRegression(unittest.TestCase):
    def test_render_escaping_and_missing_vars(self):
        store, r = make({"footer": "<footer>(c) {{ year }}</footer>",
                         "page": '<h1>{{ title }}</h1>{%include "footer"%}'})
        self.assertEqual(r.render("page", {"title": "<b>&", "year": 2025}),
                         "<h1>&lt;b&gt;&amp;</h1><footer>(c) 2025</footer>")
        self.assertEqual(r.render("page"), "<h1></h1><footer>(c) </footer>")

    def test_own_change_and_direct_include(self):
        store, r = make({"footer": "F", "page": 'P{% include "footer" %}'})
        r.render("page")
        store.set("page", 'Q{% include "footer" %}')
        self.assertEqual(r.render("page"), "QF")
        store.set("footer", "G")
        self.assertEqual(r.render("page"), "QG")

    def test_repeat_render_uses_cache(self):
        store, r = make({"footer": "F", "page": 'P{% include "footer" %}{% include "footer" %}'})
        self.assertEqual(r.render("page"), "PFF")
        n = r.compile_count
        r.render("page")
        r.render("footer")
        self.assertEqual(r.compile_count, n)

    def test_clear(self):
        store, r = make({"page": "P"})
        r.render("page")
        n = r.compile_count
        r.clear()
        r.render("page")
        self.assertEqual(r.compile_count, n + 1)


if __name__ == "__main__":
    unittest.main()
