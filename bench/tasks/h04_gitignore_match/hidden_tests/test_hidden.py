"""Hidden tests for h04_gitignore_match. Every expectation was checked against real git."""
import unittest

from ignorematch import is_ignored

# name -> (gitignore lines, [(path, is_dir, expected_ignored), ...])
CASES = {
    "no_slash_matches_at_any_level": (
        ["*.log"],
        [("debug.log", False, True), ("a/b/c.log", False, True),
         ("a/b.log.txt", False, False), ("log", False, False)]),
    "leading_slash_anchors_to_root": (
        ["/build"],
        [("build", False, True), ("src/build", False, False), ("build/out.o", False, True)]),
    "trailing_slash_matches_directories_only": (
        ["build/"],
        [("build", False, False), ("build", True, True), ("build/x.o", False, True),
         ("src/build/y", False, True), ("src/build", True, True)]),
    "middle_slash_anchors": (
        ["doc/frotz/"],
        [("doc/frotz/a.txt", False, True), ("a/doc/frotz/b.txt", False, False),
         ("doc/frotz", True, True)]),
    "dir_pattern_without_inner_slash_at_any_level": (
        ["frotz/"],
        [("frotz/a", False, True), ("a/frotz/b.txt", False, True), ("a/frotz", False, False)]),
    "star_does_not_cross_slash": (
        ["doc/*.txt"],
        [("doc/a.txt", False, True), ("doc/sub/a.txt", False, False), ("x/doc/a.txt", False, False)]),
    "dir_star_ignores_nested_through_parent": (
        ["foo/*"],
        [("foo/test.json", False, True), ("foo/bar/hello.c", False, True), ("foo", False, False)]),
    "leading_double_star": (
        ["**/foo"],
        [("foo", False, True), ("a/b/foo", False, True), ("a/foo/x", False, True),
         ("afoo", False, False)]),
    "leading_double_star_two_components": (
        ["**/foo/bar"],
        [("x/foo/bar", False, True), ("foo/bar", False, True), ("foo/x/bar", False, False)]),
    "trailing_double_star": (
        ["abc/**"],
        [("abc/x", False, True), ("abc/d/e", False, True), ("abc", False, False),
         ("x/abc/y", False, False)]),
    "middle_double_star": (
        ["a/**/b"],
        [("a/b", False, True), ("a/x/b", False, True), ("a/x/y/b", False, True),
         ("a/xb", False, False)]),
    "double_star_inside_name_is_plain_star": (
        ["x/foo**bar"],
        [("x/fooqbar", False, True), ("x/foo/bar", False, False)]),
    "negation_reincludes": (
        ["*.log", "!important.log"],
        [("debug.log", False, True), ("important.log", False, False),
         ("a/important.log", False, False)]),
    "cannot_reinclude_inside_excluded_directory": (
        ["logs/", "!logs/keep.log"],
        [("logs/keep.log", False, True), ("logs/x.log", False, True)]),
    "can_reinclude_when_only_contents_excluded": (
        ["logs/*", "!logs/keep.log"],
        [("logs/keep.log", False, False), ("logs/x.log", False, True)]),
    "last_match_wins": (
        ["!a.txt", "*.txt"],
        [("a.txt", False, True)]),
    "only_foo_bar_example": (
        ["/*", "!/foo", "/foo/*", "!/foo/bar"],
        [("foo/bar/x", False, False), ("foo/bar", False, False), ("foo/baz", False, True),
         ("top.txt", False, True)]),
    "comments_blank_lines_and_escaped_prefixes": (
        ["# comment", "", "\\#hash", "\\!bang"],
        [("# comment", False, False), ("comment", False, False), ("#hash", False, True),
         ("!bang", False, True)]),
    "trailing_spaces_trimmed_unless_escaped": (
        ["foo   ", "bar\\ "],
        [("foo", False, True), ("bar ", False, True), ("bar", False, False)]),
    "question_mark_and_brackets": (
        ["file?.txt", "[a-c]*.py", "[!a]x"],
        [("file1.txt", False, True), ("file10.txt", False, False), ("b1.py", False, True),
         ("d1.py", False, False), ("bx", False, True), ("ax", False, False)]),
    "escaped_wildcard_is_literal": (
        ["foo\\*"],
        [("foo*", False, True), ("foox", False, False)]),
    "negated_directory_pattern": (
        ["build/", "!build/"],
        [("build/x", False, False)]),
    "plain_name_matches_directory_contents": (
        ["node_modules"],
        [("a/node_modules/b/c.js", False, True), ("node_modules", True, True)]),
    "double_star_directory_only": (
        ["**/cache/"],
        [("a/cache/f", False, True), ("a/cache", False, False), ("cache/f", False, True)]),
}


class TestGitignore(unittest.TestCase):
    pass


def _make(patterns, checks):
    def test(self):
        for path, is_dir, expected in checks:
            with self.subTest(path=path, is_dir=is_dir):
                self.assertIs(bool(is_ignored(path, list(patterns), is_dir=is_dir)), expected,
                              f"patterns={patterns!r} path={path!r} is_dir={is_dir}")
    return test


for _name, (_patterns, _checks) in CASES.items():
    setattr(TestGitignore, "test_" + _name, _make(_patterns, _checks))


class TestNoPatterns(unittest.TestCase):
    def test_empty_patterns(self):
        self.assertFalse(is_ignored("a/b.txt", []))


if __name__ == "__main__":
    unittest.main()
