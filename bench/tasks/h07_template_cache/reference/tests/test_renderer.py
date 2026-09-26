import unittest

from sitegen import Renderer, TemplateError, TemplateNotFound, TemplateStore


class TestRender(unittest.TestCase):
    def setUp(self):
        self.store = TemplateStore({
            "footer": "<footer>(c) {{ year }}</footer>",
            "page": '<h1>{{ title }}</h1>{% include "footer" %}',
        })
        self.r = Renderer(self.store)

    def test_render(self):
        self.assertEqual(self.r.render("page", {"title": "Hi", "year": 2025}),
                         "<h1>Hi</h1><footer>(c) 2025</footer>")

    def test_escaping_and_missing(self):
        self.assertEqual(self.r.render("page", {"title": "<b>"}),
                         "<h1>&lt;b&gt;</h1><footer>(c) </footer>")

    def test_cached(self):
        self.r.render("page")
        n = self.r.compile_count
        self.r.render("page")
        self.r.render("footer")
        self.assertEqual(self.r.compile_count, n)

    def test_direct_include_updates(self):
        self.r.render("page")
        self.store.set("footer", "<footer>new</footer>")
        self.assertEqual(self.r.render("page", {"title": "x"}), "<h1>x</h1><footer>new</footer>")

    def test_missing(self):
        with self.assertRaises(TemplateNotFound):
            self.r.render("nope")

    def test_cycle(self):
        self.store.set("a", '{% include "b" %}')
        self.store.set("b", '{% include "a" %}')
        with self.assertRaises(TemplateError):
            self.r.render("a")


if __name__ == "__main__":
    unittest.main()
