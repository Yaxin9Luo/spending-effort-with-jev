"""Apply JSON Patch documents to parsed JSON values.

Used by the config service: clients send a patch, we apply it to the
stored document (already parsed with json.loads) and store the result.

Implements RFC 6902 with RFC 6901 JSON Pointers.
"""
import copy
import re

_INDEX_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_MISSING = object()


class JsonPatchError(Exception):
    """Raised when a patch cannot be applied."""


def _parse_pointer(pointer):
    if not isinstance(pointer, str):
        raise JsonPatchError(f"pointer must be a string: {pointer!r}")
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise JsonPatchError(f"pointer must start with '/': {pointer!r}")
    tokens = []
    for raw in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise JsonPatchError(f"invalid escape in pointer: {pointer!r}")
        tokens.append(raw.replace("~1", "/").replace("~0", "~"))
    return tokens


def _array_index(arr, token, allow_end):
    if token == "-":
        if allow_end:
            return len(arr)
        raise JsonPatchError("'-' refers to a nonexistent element")
    if not _INDEX_RE.match(token):
        raise JsonPatchError(f"invalid array index: {token!r}")
    i = int(token)
    limit = len(arr) if allow_end else len(arr) - 1
    if i > limit:
        raise JsonPatchError(f"array index out of range: {token}")
    return i


def _resolve(doc, tokens):
    cur = doc
    for tok in tokens:
        if isinstance(cur, dict):
            if tok not in cur:
                raise JsonPatchError(f"member not found: {tok!r}")
            cur = cur[tok]
        elif isinstance(cur, list):
            cur = cur[_array_index(cur, tok, allow_end=False)]
        else:
            raise JsonPatchError(f"cannot traverse into scalar at {tok!r}")
    return cur


def _parent(doc, tokens):
    parent = _resolve(doc, tokens[:-1])
    if not isinstance(parent, (dict, list)):
        raise JsonPatchError("parent is not a container")
    return parent, tokens[-1]


def _add(doc, tokens, value):
    if not tokens:
        return value
    parent, key = _parent(doc, tokens)
    if isinstance(parent, dict):
        parent[key] = value
    else:
        parent.insert(_array_index(parent, key, allow_end=True), value)
    return doc


def _remove(doc, tokens):
    if not tokens:
        raise JsonPatchError("cannot remove the whole document")
    parent, key = _parent(doc, tokens)
    if isinstance(parent, dict):
        if key not in parent:
            raise JsonPatchError(f"member not found: {key!r}")
        return parent.pop(key)
    return parent.pop(_array_index(parent, key, allow_end=False))


def _replace(doc, tokens, value):
    if not tokens:
        return value
    parent, key = _parent(doc, tokens)
    if isinstance(parent, dict):
        if key not in parent:
            raise JsonPatchError(f"member not found: {key!r}")
        parent[key] = value
    else:
        parent[_array_index(parent, key, allow_end=False)] = value
    return doc


def _json_equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    return False


def _member(op, name):
    if name not in op:
        raise JsonPatchError(f"operation missing {name!r}: {op!r}")
    return op[name]


def apply_patch(doc, patch):
    """Apply `patch` (a list of operation dicts) to `doc` and return the result.

    The input document is never modified; if any operation fails the whole
    patch is rejected with JsonPatchError.
    """
    if not isinstance(patch, list):
        raise JsonPatchError("patch must be a list of operations")
    result = copy.deepcopy(doc)
    for op in patch:
        if not isinstance(op, dict):
            raise JsonPatchError(f"operation must be an object: {op!r}")
        name = _member(op, "op")
        path = _parse_pointer(_member(op, "path"))
        if name == "add":
            result = _add(result, path, copy.deepcopy(_member(op, "value")))
        elif name == "remove":
            _remove(result, path)
        elif name == "replace":
            value = copy.deepcopy(_member(op, "value"))
            _resolve(result, path)
            result = _replace(result, path, value)
        elif name == "move":
            src = _parse_pointer(_member(op, "from"))
            if src == path:
                _resolve(result, src)
                continue
            if len(src) < len(path) and path[:len(src)] == src:
                raise JsonPatchError("cannot move a value into one of its children")
            _resolve(result, src)
            value = _remove(result, src)
            result = _add(result, path, value)
        elif name == "copy":
            src = _parse_pointer(_member(op, "from"))
            value = copy.deepcopy(_resolve(result, src))
            result = _add(result, path, value)
        elif name == "test":
            expected = _member(op, "value")
            if not _json_equal(_resolve(result, path), expected):
                raise JsonPatchError(f"test failed at {op['path']!r}")
        else:
            raise JsonPatchError(f"unknown op: {name!r}")
    return result
