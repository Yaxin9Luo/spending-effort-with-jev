"""Decide which files the bundler should skip, using the repo's .gitignore.

Follows gitignore(5): blank lines and '#' comments, trailing-space trimming,
'!' negation with last-match-wins, trailing '/' for directories only,
patterns without a '/' matching at any depth, '*', '?', '[...]', '**', and
backslash escapes.  A path inside an excluded directory is ignored no matter
what later patterns say, because git never looks inside that directory.
"""


def _trim_trailing_spaces(line):
    last_space = None
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == " ":
            if last_space is None:
                last_space = i
        elif ch == "\\":
            i += 1
            if i >= len(line):
                return line
            last_space = None
        else:
            last_space = None
        i += 1
    return line if last_space is None else line[:last_space]


class _Pattern:
    def __init__(self, text, negated, dir_only, basename_only):
        self.text = text
        self.negated = negated
        self.dir_only = dir_only
        self.basename_only = basename_only

    def matches(self, path, is_dir):
        if self.dir_only and not is_dir:
            return False
        if self.basename_only:
            return _wildmatch(self.text, path.rsplit("/", 1)[-1])
        return _wildmatch(self.text, path)


def _parse(lines):
    out = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line or line.startswith("#"):
            continue
        line = _trim_trailing_spaces(line)
        if not line:
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        dir_only = line.endswith("/")
        if dir_only:
            line = line[:-1]
        if not line:
            continue
        basename_only = "/" not in line
        if line.startswith("/"):
            line = line[1:]
        out.append(_Pattern(line, negated, dir_only, basename_only))
    return out


def _match_bracket(pat, pi, ch):
    """Match a [...] class starting at pat[pi] == '['. Returns (matched, next_pi) or (None, None)."""
    i = pi + 1
    negate = False
    if i < len(pat) and pat[i] in "!^":
        negate = True
        i += 1
    matched = False
    first = True
    while i < len(pat):
        c = pat[i]
        if c == "]" and not first:
            if ch == "/":
                return False, i + 1
            return matched != negate, i + 1
        first = False
        if c == "[" and pat.startswith("[:", i):
            end = pat.find(":]", i + 2)
            if end != -1:
                cls = pat[i + 2:end]
                test = {
                    "alnum": str.isalnum, "alpha": str.isalpha, "digit": str.isdigit,
                    "lower": str.islower, "upper": str.isupper, "space": str.isspace,
                    "punct": lambda s: s.isprintable() and not s.isalnum() and not s.isspace(),
                    "xdigit": lambda s: s in "0123456789abcdefABCDEF",
                    "blank": lambda s: s in " \t", "print": str.isprintable,
                    "graph": lambda s: s.isprintable() and s != " ",
                    "cntrl": lambda s: not s.isprintable(),
                }.get(cls)
                if test is None:
                    return None, None
                if ch.isascii() and test(ch):
                    matched = True
                i = end + 2
                continue
        if c == "\\" and i + 1 < len(pat):
            i += 1
            c = pat[i]
        lo = c
        if i + 2 < len(pat) and pat[i + 1] == "-" and pat[i + 2] != "]":
            hi = pat[i + 2]
            i += 2
            if hi == "\\" and i + 1 < len(pat):
                i += 1
                hi = pat[i]
            if lo <= ch <= hi:
                matched = True
        elif ch == lo:
            matched = True
        i += 1
    return None, None  # unterminated class


def _wildmatch(pat, text):
    """git's wildmatch() with WM_PATHNAME."""
    memo = {}

    def m(pi, ti):
        key = (pi, ti)
        if key in memo:
            return memo[key]
        memo[key] = res = _m(pi, ti)
        return res

    def _m(pi, ti):
        while pi < len(pat):
            c = pat[pi]
            if c == "*":
                start = pi
                while pi < len(pat) and pat[pi] == "*":
                    pi += 1
                double = pi - start >= 2
                at_seg_start = start == 0 or pat[start - 1] == "/"
                at_seg_end = pi == len(pat) or pat[pi] == "/"
                if double and at_seg_start and at_seg_end:
                    if pi == len(pat):
                        return True
                    # "**/" matches zero or more whole directories
                    rest = pi + 1
                    if m(rest, ti):
                        return True
                    for j in range(ti, len(text)):
                        if text[j] == "/" and m(rest, j + 1):
                            return True
                    return False
                # plain star: anything except '/'
                for j in range(ti, len(text) + 1):
                    if m(pi, j):
                        return True
                    if j < len(text) and text[j] == "/":
                        break
                return False
            if ti >= len(text):
                return False
            ch = text[ti]
            if c == "?":
                if ch == "/":
                    return False
            elif c == "[":
                ok, nxt = _match_bracket(pat, pi, ch)
                if ok is None:
                    if ch != "[":
                        return False
                else:
                    if not ok:
                        return False
                    pi, ti = nxt, ti + 1
                    continue
            elif c == "\\" and pi + 1 < len(pat):
                pi += 1
                if pat[pi] != ch:
                    return False
            elif c != ch:
                return False
            pi += 1
            ti += 1
        return ti == len(text)

    return m(0, 0)


def _excluded(patterns, path, is_dir):
    for p in reversed(patterns):
        if p.matches(path, is_dir):
            return not p.negated
    return False


def is_ignored(path, patterns, is_dir=False):
    """Return True if git would ignore `path`.

    path     -- path relative to the repository root, '/'-separated, no leading './'
    patterns -- the lines of the repository's top-level .gitignore
    is_dir   -- True if `path` itself is a directory
    """
    compiled = _parse(patterns)
    parts = path.strip("/").split("/")
    for i in range(1, len(parts)):
        if _excluded(compiled, "/".join(parts[:i]), True):
            return True
    return _excluded(compiled, "/".join(parts), is_dir)
