"""Semver helpers for the internal package index.

The index has to resolve dependency ranges written for npm, so range
evaluation must agree with what npm itself would pick.

Semantics follow node-semver with default options (not loose,
includePrerelease off).
"""
import re

_NUM = r"0|[1-9]\d*"
_PRE_ID = r"(?:0|[1-9]\d*|\d*[a-zA-Z-][a-zA-Z0-9-]*)"
_PRE = rf"{_PRE_ID}(?:\.{_PRE_ID})*"
_BUILD = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"

_VERSION_RE = re.compile(
    rf"^v?({_NUM})\.({_NUM})\.({_NUM})(?:-({_PRE}))?(?:\+({_BUILD}))?$")

_XR = rf"(?:[xX*]|{_NUM})"
_PARTIAL = (rf"v?({_XR})(?:\.({_XR})(?:\.({_XR})"
            rf"(?:-({_PRE}))?(?:\+{_BUILD})?)?)?")
_SIMPLE_RE = re.compile(rf"^(\^|~|[<>]=?|=)?{_PARTIAL}$")
_HYPHEN_RE = re.compile(rf"^{_PARTIAL}\s+-\s+{_PARTIAL}$")


class _Invalid(ValueError):
    pass


def _parse_pre(s):
    if s is None:
        return ()
    return tuple(int(p) if p.isdigit() else p for p in s.split("."))


def _parse_version(s):
    if not isinstance(s, str):
        raise _Invalid(s)
    m = _VERSION_RE.match(s.strip())
    if not m:
        raise _Invalid(s)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), _parse_pre(m.group(4)))


def _cmp_pre_id(a, b):
    a_num, b_num = isinstance(a, int), isinstance(b, int)
    if a_num and b_num:
        return (a > b) - (a < b)
    if a_num:
        return -1
    if b_num:
        return 1
    return (a > b) - (a < b)


def _compare(a, b):
    ka, kb = a[:3], b[:3]
    if ka != kb:
        return -1 if ka < kb else 1
    pa, pb = a[3], b[3]
    if not pa and not pb:
        return 0
    if not pa:
        return 1
    if not pb:
        return -1
    for x, y in zip(pa, pb):
        c = _cmp_pre_id(x, y)
        if c:
            return c
    return (len(pa) > len(pb)) - (len(pa) < len(pb))


_ZERO_PRE = (0,)
_NOTHING = ("<", (0, 0, 0, _ZERO_PRE))


def _is_x(p):
    return p is None or p in ("x", "X", "*")


def _v(M, m, p, pre=()):
    return (int(M), int(m), int(p), pre)


def _caret(M, m, p, pre):
    if _is_x(M):
        return []
    M = int(M)
    if _is_x(m):
        return [(">=", _v(M, 0, 0)), ("<", _v(M + 1, 0, 0, _ZERO_PRE))]
    m = int(m)
    if _is_x(p):
        if M == 0:
            return [(">=", _v(M, m, 0)), ("<", _v(M, m + 1, 0, _ZERO_PRE))]
        return [(">=", _v(M, m, 0)), ("<", _v(M + 1, 0, 0, _ZERO_PRE))]
    p = int(p)
    lo = (">=", _v(M, m, p, _parse_pre(pre)))
    if M == 0:
        if m == 0:
            return [lo, ("<", _v(M, m, p + 1, _ZERO_PRE))]
        return [lo, ("<", _v(M, m + 1, 0, _ZERO_PRE))]
    return [lo, ("<", _v(M + 1, 0, 0, _ZERO_PRE))]


def _tilde(M, m, p, pre):
    if _is_x(M):
        return []
    M = int(M)
    if _is_x(m):
        return [(">=", _v(M, 0, 0)), ("<", _v(M + 1, 0, 0, _ZERO_PRE))]
    m = int(m)
    if _is_x(p):
        return [(">=", _v(M, m, 0)), ("<", _v(M, m + 1, 0, _ZERO_PRE))]
    return [(">=", _v(M, m, int(p), _parse_pre(pre))), ("<", _v(M, m + 1, 0, _ZERO_PRE))]


def _xrange(op, M, m, p, pre):
    if op == "=":
        op = ""
    any_x = _is_x(M) or _is_x(m) or _is_x(p)
    if not any_x:
        return [(op or "=", _v(M, m, p, _parse_pre(pre)))]
    if _is_x(M):
        if op in (">", "<"):
            return [_NOTHING]
        return []
    M = int(M)
    xm = _is_x(m)
    m = 0 if xm else int(m)
    if op:
        p = 0
        if op == ">":
            op = ">="
            if xm:
                M, m = M + 1, 0
            else:
                m += 1
        elif op == "<=":
            op = "<"
            if xm:
                M += 1
            else:
                m += 1
        return [(op, _v(M, m, p, _ZERO_PRE if op == "<" else ()))]
    if xm:
        return [(">=", _v(M, 0, 0)), ("<", _v(M + 1, 0, 0, _ZERO_PRE))]
    return [(">=", _v(M, m, 0)), ("<", _v(M, m + 1, 0, _ZERO_PRE))]


def _hyphen(fM, fm, fp, fpre, tM, tm, tp, tpre):
    out = []
    if _is_x(fM):
        pass
    elif _is_x(fm):
        out.append((">=", _v(fM, 0, 0)))
    elif _is_x(fp):
        out.append((">=", _v(fM, fm, 0)))
    else:
        out.append((">=", _v(fM, fm, fp, _parse_pre(fpre))))
    if _is_x(tM):
        pass
    elif _is_x(tm):
        out.append(("<", _v(int(tM) + 1, 0, 0, _ZERO_PRE)))
    elif _is_x(tp):
        out.append(("<", _v(tM, int(tm) + 1, 0, _ZERO_PRE)))
    else:
        out.append(("<=", _v(tM, tm, tp, _parse_pre(tpre))))
    return out


def _parse_comparator_set(text):
    text = text.strip()
    if text == "":
        return []
    m = _HYPHEN_RE.match(text)
    if m:
        return _hyphen(*m.groups())
    out = []
    for tok in text.split():
        m = _SIMPLE_RE.match(tok)
        if not m:
            raise _Invalid(tok)
        op, M, mi, p, pre = m.groups()
        if op == "^":
            out.extend(_caret(M, mi, p, pre))
        elif op == "~":
            out.extend(_tilde(M, mi, p, pre))
        else:
            out.extend(_xrange(op or "", M, mi, p, pre))
    return out


def _parse_range(range_):
    if not isinstance(range_, str):
        raise _Invalid(range_)
    return [_parse_comparator_set(part) for part in re.split(r"\s*\|\|\s*", range_.strip())]


def _test_comparator(op, target, v):
    c = _compare(v, target)
    return {"=": c == 0, "<": c < 0, "<=": c <= 0, ">": c > 0, ">=": c >= 0}[op]


def _test_set(cset, v):
    if not all(_test_comparator(op, t, v) for op, t in cset):
        return False
    if v[3]:
        return any(t[3] and t[:3] == v[:3] for _, t in cset)
    return True


def _test(sets, v):
    return any(_test_set(s, v) for s in sets)


def satisfies(version, range_):
    """Return True if `version` (a string) satisfies `range_` (a string)."""
    try:
        v = _parse_version(version)
        sets = _parse_range(range_)
    except _Invalid:
        return False
    return _test(sets, v)


def max_satisfying(versions, range_):
    """Return the highest version string in `versions` that satisfies `range_`, or None."""
    try:
        sets = _parse_range(range_)
    except _Invalid:
        return None
    best = best_v = None
    for s in versions:
        try:
            v = _parse_version(s)
        except _Invalid:
            continue
        if _test(sets, v) and (best_v is None or _compare(v, best_v) > 0):
            best, best_v = s, v
    return best
