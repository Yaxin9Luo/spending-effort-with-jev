"""Hidden tests for h02_json_patch (RFC 6902 + RFC 6901)."""
import copy
import unittest

from jsonpatch_lite import JsonPatchError, apply_patch


class Base(unittest.TestCase):
    def ok(self, doc, patch, expected):
        self.assertEqual(apply_patch(doc, patch), expected)

    def fails(self, doc, patch):
        with self.assertRaises(JsonPatchError):
            apply_patch(doc, patch)


class TestAdd(Base):
    def test_add_object_member(self):
        self.ok({"foo": "bar"}, [{"op": "add", "path": "/baz", "value": "qux"}],
                {"foo": "bar", "baz": "qux"})

    def test_add_existing_member_replaces(self):
        self.ok({"foo": "bar"}, [{"op": "add", "path": "/foo", "value": 1}], {"foo": 1})

    def test_add_array_insert_shifts(self):
        self.ok({"foo": ["bar", "baz"]}, [{"op": "add", "path": "/foo/1", "value": "qux"}],
                {"foo": ["bar", "qux", "baz"]})

    def test_add_dash_appends(self):
        self.ok({"foo": [1, 2]}, [{"op": "add", "path": "/foo/-", "value": 3}], {"foo": [1, 2, 3]})
        self.ok([], [{"op": "add", "path": "/-", "value": "x"}], ["x"])

    def test_add_index_equal_to_length_appends(self):
        self.ok({"foo": [1, 2]}, [{"op": "add", "path": "/foo/2", "value": 3}], {"foo": [1, 2, 3]})

    def test_add_index_past_end_fails(self):
        self.fails({"foo": [1, 2]}, [{"op": "add", "path": "/foo/3", "value": 3}])
        self.fails([], [{"op": "add", "path": "/1", "value": 3}])

    def test_add_nonexistent_parent_fails(self):
        self.fails({"foo": "bar"}, [{"op": "add", "path": "/baz/bat", "value": "qux"}])

    def test_add_root_replaces_document(self):
        self.ok({"foo": "bar"}, [{"op": "add", "path": "", "value": [1, 2]}], [1, 2])

    def test_add_empty_string_key(self):
        self.ok({"a": 1}, [{"op": "add", "path": "/", "value": 2}], {"a": 1, "": 2})

    def test_add_null_value(self):
        self.ok({"a": 1}, [{"op": "add", "path": "/b", "value": None}], {"a": 1, "b": None})

    def test_add_nested_array_value(self):
        self.ok({"foo": ["bar"]}, [{"op": "add", "path": "/foo/1", "value": ["abc", "def"]}],
                {"foo": ["bar", ["abc", "def"]]})


class TestPointers(Base):
    def test_escapes(self):
        doc = {"a/b": 1, "m~n": 2}
        self.ok(doc, [{"op": "replace", "path": "/a~1b", "value": 10},
                      {"op": "replace", "path": "/m~0n", "value": 20}],
                {"a/b": 10, "m~n": 20})

    def test_escape_decoding_order(self):
        doc = {"~1": "tilde-one", "/": "slash"}
        self.ok(doc, [{"op": "remove", "path": "/~01"}], {"/": "slash"})

    def test_invalid_pointers(self):
        self.fails({"a": 1}, [{"op": "replace", "path": "a", "value": 2}])
        self.fails({"a~2b": 1}, [{"op": "remove", "path": "/a~2b"}])

    def test_bad_array_indices(self):
        doc = {"arr": [0, 1, 2]}
        for tok in ("01", "-1", "1e0", "x", " 1"):
            with self.subTest(tok=tok):
                self.fails(doc, [{"op": "replace", "path": "/arr/" + tok, "value": 9}])

    def test_dash_is_an_ordinary_key_in_objects(self):
        self.ok({"foo": {}}, [{"op": "add", "path": "/foo/-", "value": 1}], {"foo": {"-": 1}})

    def test_numeric_token_on_object_is_a_key(self):
        self.ok({"0": "a"}, [{"op": "replace", "path": "/0", "value": "b"}], {"0": "b"})

    def test_traversing_into_scalar_fails(self):
        self.fails({"a": "str"}, [{"op": "add", "path": "/a/b", "value": 1}])
        self.fails({"a": 5}, [{"op": "test", "path": "/a/0", "value": 1}])


class TestRemoveReplace(Base):
    def test_remove_member_and_element(self):
        self.ok({"baz": "qux", "foo": "bar"}, [{"op": "remove", "path": "/baz"}], {"foo": "bar"})
        self.ok({"foo": ["bar", "qux", "baz"]}, [{"op": "remove", "path": "/foo/1"}],
                {"foo": ["bar", "baz"]})

    def test_remove_missing_fails(self):
        self.fails({"foo": "bar"}, [{"op": "remove", "path": "/baz"}])
        self.fails({"foo": [1]}, [{"op": "remove", "path": "/foo/1"}])

    def test_remove_dash_fails(self):
        self.fails({"foo": [1, 2]}, [{"op": "remove", "path": "/foo/-"}])

    def test_replace(self):
        self.ok({"baz": "qux", "foo": "bar"}, [{"op": "replace", "path": "/baz", "value": "boo"}],
                {"baz": "boo", "foo": "bar"})
        self.ok([1, 2, 3], [{"op": "replace", "path": "/1", "value": 9}], [1, 9, 3])

    def test_replace_missing_fails(self):
        self.fails({"foo": "bar"}, [{"op": "replace", "path": "/baz", "value": 1}])
        self.fails([1, 2], [{"op": "replace", "path": "/2", "value": 1}])
        self.fails([1, 2], [{"op": "replace", "path": "/-", "value": 1}])

    def test_replace_root(self):
        self.ok({"a": 1}, [{"op": "replace", "path": "", "value": {"b": 2}}], {"b": 2})


class TestMoveCopy(Base):
    def test_move_member(self):
        doc = {"foo": {"bar": "baz", "waldo": "fred"}, "qux": {"corge": "grault"}}
        self.ok(doc, [{"op": "move", "from": "/foo/waldo", "path": "/qux/thud"}],
                {"foo": {"bar": "baz"}, "qux": {"corge": "grault", "thud": "fred"}})

    def test_move_array_element(self):
        self.ok({"foo": ["all", "grass", "cows", "eat"]},
                [{"op": "move", "from": "/foo/1", "path": "/foo/3"}],
                {"foo": ["all", "cows", "eat", "grass"]})

    def test_move_into_own_child_fails(self):
        self.fails({"a": {"b": {}}}, [{"op": "move", "from": "/a", "path": "/a/b/c"}])

    def test_move_to_path_sharing_string_prefix(self):
        self.ok({"a": 1}, [{"op": "move", "from": "/a", "path": "/ab"}], {"ab": 1})

    def test_move_to_same_path_is_noop(self):
        self.ok({"a": {"b": 1}}, [{"op": "move", "from": "/a", "path": "/a"}], {"a": {"b": 1}})

    def test_move_missing_from_fails(self):
        self.fails({"a": 1}, [{"op": "move", "from": "/nope", "path": "/b"}])

    def test_copy_is_independent(self):
        doc = {"a": {"x": [1]}}
        out = apply_patch(doc, [{"op": "copy", "from": "/a", "path": "/b"},
                                {"op": "add", "path": "/b/x/-", "value": 2}])
        self.assertEqual(out, {"a": {"x": [1]}, "b": {"x": [1, 2]}})

    def test_copy_missing_from_fails(self):
        self.fails({"a": 1}, [{"op": "copy", "from": "/nope", "path": "/b"}])


class TestTestOp(Base):
    def test_success_then_continue(self):
        doc = {"baz": "qux", "foo": ["a", 2, "c"]}
        self.ok(doc, [{"op": "test", "path": "/baz", "value": "qux"},
                      {"op": "test", "path": "/foo/1", "value": 2},
                      {"op": "add", "path": "/ok", "value": True}],
                {"baz": "qux", "foo": ["a", 2, "c"], "ok": True})

    def test_mismatch_fails(self):
        self.fails({"baz": "qux"}, [{"op": "test", "path": "/baz", "value": "bar"}])

    def test_numbers_compare_by_value(self):
        self.ok({"n": 1}, [{"op": "test", "path": "/n", "value": 1.0}], {"n": 1})

    def test_booleans_are_not_numbers(self):
        self.fails({"n": 1}, [{"op": "test", "path": "/n", "value": True}])
        self.fails({"n": False}, [{"op": "test", "path": "/n", "value": 0}])
        self.fails({"n": [1, {"k": 0}]}, [{"op": "test", "path": "/n", "value": [True, {"k": False}]}])

    def test_null_is_not_missing(self):
        self.ok({"n": None}, [{"op": "test", "path": "/n", "value": None}], {"n": None})
        self.fails({}, [{"op": "test", "path": "/n", "value": None}])

    def test_structural_equality(self):
        self.ok({"o": {"a": 1, "b": [1, 2]}},
                [{"op": "test", "path": "/o", "value": {"b": [1, 2], "a": 1}}],
                {"o": {"a": 1, "b": [1, 2]}})
        self.fails({"o": [1, 2]}, [{"op": "test", "path": "/o", "value": [2, 1]}])


class TestPatchLevel(Base):
    def test_malformed_operations(self):
        for op in ({"op": "frobnicate", "path": "/a"},
                   {"op": "add", "value": 1},
                   {"path": "/a", "value": 1},
                   {"op": "add", "path": "/b"},
                   {"op": "replace", "path": "/a"},
                   {"op": "move", "path": "/b"},
                   {"op": "copy", "path": "/b"}):
            with self.subTest(op=op):
                self.fails({"a": 1}, [op])

    def test_extra_members_ignored(self):
        self.ok({"a": 1}, [{"op": "add", "path": "/b", "value": 2, "from": "/zzz", "note": "x"}],
                {"a": 1, "b": 2})

    def test_failure_is_atomic(self):
        doc = {"a": [1, 2], "b": {"c": 1}}
        before = copy.deepcopy(doc)
        with self.assertRaises(JsonPatchError):
            apply_patch(doc, [{"op": "add", "path": "/a/-", "value": 3},
                              {"op": "remove", "path": "/b/c"},
                              {"op": "test", "path": "/a/0", "value": 99}])
        self.assertEqual(doc, before)

    def test_success_does_not_mutate_input(self):
        doc = {"a": [1, 2], "b": {"c": 1}}
        before = copy.deepcopy(doc)
        apply_patch(doc, [{"op": "add", "path": "/a/0", "value": 0},
                          {"op": "replace", "path": "/b/c", "value": 5},
                          {"op": "move", "from": "/b", "path": "/d"}])
        self.assertEqual(doc, before)

    def test_operations_apply_in_sequence(self):
        self.ok({}, [{"op": "add", "path": "/a", "value": []},
                     {"op": "add", "path": "/a/-", "value": {"x": 1}},
                     {"op": "copy", "from": "/a/0", "path": "/a/-"},
                     {"op": "replace", "path": "/a/1/x", "value": 2},
                     {"op": "test", "path": "/a/0/x", "value": 1}],
                {"a": [{"x": 1}, {"x": 2}]})


if __name__ == "__main__":
    unittest.main()
