import unittest

from minitemplate import TemplateError, render


class User:
    def __init__(self, name, email=None):
        self.name = name
        self.email = email


class TestLookup(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(render("hello world } { }", {}), "hello world } { }")

    def test_simple_and_whitespace(self):
        ctx = {"name": "Ann"}
        self.assertEqual(render("{{name}}|{{ name }}|{{   name   }}", ctx), "Ann|Ann|Ann")

    def test_adjacent_tags_and_text(self):
        self.assertEqual(render("[{{a}}{{b}}]-{{ a }}", {"a": 1, "b": 2}), "[12]-1")

    def test_dict_path(self):
        ctx = {"user": {"profile": {"city": "Oslo"}}}
        self.assertEqual(render("{{ user.profile.city }}", ctx), "Oslo")

    def test_attribute_path(self):
        self.assertEqual(render("{{ u.name }}", {"u": User("Bo")}), "Bo")

    def test_mixed_path_with_index(self):
        ctx = {"orders": [{"id": 5}, {"id": 6, "owner": User("Cy")}]}
        self.assertEqual(render("{{ orders.1.id }} {{ orders.1.owner.name }} {{ orders.0.id }}", ctx), "6 Cy 5")

    def test_tuple_index(self):
        self.assertEqual(render("{{ t.0 }}", {"t": ("x", "y")}), "x")

    def test_missing_raises(self):
        for tpl, ctx in [("{{ nope }}", {}), ("{{ a.b }}", {"a": {}}), ("{{ u.age }}", {"u": User("x")}),
                         ("{{ l.5 }}", {"l": [1]})]:
            with self.subTest(tpl=tpl):
                with self.assertRaises(TemplateError):
                    render(tpl, ctx)

    def test_non_string_values(self):
        self.assertEqual(render("{{ n }} {{ f }} {{ b }}", {"n": 3, "f": 1.5, "b": True}), "3 1.5 True")

    def test_none_renders_empty(self):
        self.assertEqual(render("[{{ x }}]", {"x": None}), "[]")
        self.assertEqual(render("[{{ u.email }}]", {"u": User("a")}), "[]")

    def test_falsy_values_render(self):
        self.assertEqual(render("{{ z }}|{{ e }}|{{ f }}", {"z": 0, "e": "", "f": False}), "0||False")


class TestFilters(unittest.TestCase):
    def test_upper_lower_trim(self):
        ctx = {"s": "  MiXeD  "}
        self.assertEqual(render("{{ s|upper }}", ctx), "  MIXED  ")
        self.assertEqual(render("{{ s|lower }}", ctx), "  mixed  ")
        self.assertEqual(render("[{{ s|trim }}]", ctx), "[MiXeD]")

    def test_chain_left_to_right(self):
        self.assertEqual(render("[{{ s|trim|upper }}]", {"s": "  ab "}), "[AB]")

    def test_filters_on_non_strings(self):
        self.assertEqual(render("{{ b|lower }}", {"b": True}), "true")

    def test_default_on_missing(self):
        self.assertEqual(render('{{ user.nick|default:"friend" }}', {"user": {}}), "friend")
        self.assertEqual(render('{{ nothing|default:"x" }}', {}), "x")

    def test_default_on_none(self):
        self.assertEqual(render('{{ x|default:"n/a" }}', {"x": None}), "n/a")

    def test_default_not_used_for_present_falsy(self):
        self.assertEqual(render('{{ x|default:"d" }}|{{ y|default:"d" }}', {"x": 0, "y": ""}), "0|")

    def test_default_with_spaces_and_colons(self):
        self.assertEqual(render('{{ t|default:"at 10:30 today" }}', {}), "at 10:30 today")

    def test_default_then_upper(self):
        self.assertEqual(render('{{ x|default:"none"|upper }}', {}), "NONE")

    def test_default_is_escaped(self):
        self.assertEqual(render('{{ x|default:"<none>" }}', {}), "&lt;none&gt;")

    def test_unknown_filter(self):
        with self.assertRaises(TemplateError):
            render("{{ x|shout }}", {"x": "a"})

    def test_emails_module(self):
        from emails import welcome_email
        self.assertEqual(welcome_email({"first_name": "Dee"}, "shop"), "<p>Hi Dee, welcome to SHOP!</p>")
        self.assertEqual(welcome_email({}, "shop"), "<p>Hi there, welcome to SHOP!</p>")


class TestEscaping(unittest.TestCase):
    def test_html_escaped(self):
        ctx = {"x": "<script>alert('x') & \"y\"</script>"}
        self.assertEqual(render("{{ x }}", ctx),
                         "&lt;script&gt;alert(&#x27;x&#x27;) &amp; &quot;y&quot;&lt;/script&gt;")

    def test_raw(self):
        self.assertEqual(render("{{ x|raw }}", {"x": "<b>&</b>"}), "<b>&</b>")

    def test_raw_with_other_filters(self):
        self.assertEqual(render("{{ x|raw|upper }}", {"x": "<b>"}), "<B>")
        self.assertEqual(render("{{ x|upper|raw }}", {"x": "<b>"}), "<B>")

    def test_template_text_not_escaped(self):
        self.assertEqual(render("<p>{{ x }}</p>", {"x": "a&b"}), "<p>a&amp;b</p>")

    def test_escaped_braces(self):
        self.assertEqual(render(r"use \{{ name }} to insert {{ name }}", {"name": "N"}),
                         "use {{ name }} to insert N")

    def test_escaped_braces_without_context(self):
        self.assertEqual(render(r"\{{ undefined }}", {}), "{{ undefined }}")


class TestErrors(unittest.TestCase):
    def test_unclosed(self):
        for tpl in ["{{ name", "hi {{ name }} and {{ other", "{{"]:
            with self.subTest(tpl=tpl):
                with self.assertRaises(TemplateError):
                    render(tpl, {"name": "a", "other": "b"})

    def test_empty_expression(self):
        for tpl in ["{{}}", "{{ }}", "{{   }}"]:
            with self.subTest(tpl=tpl):
                with self.assertRaises(TemplateError):
                    render(tpl, {})


if __name__ == "__main__":
    unittest.main()
