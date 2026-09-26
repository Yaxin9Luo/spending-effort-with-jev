"""Tiny template renderer for notification emails."""
import html
import re


class TemplateError(Exception):
    pass


_MISSING = object()
_DEFAULT_RE = re.compile(r'^default:"(.*)"$', re.S)


def _split_filters(expr):
    """Split on | outside double quotes."""
    parts, buf, in_q = [], [], False
    for ch in expr:
        if ch == '"':
            in_q = not in_q
        if ch == "|" and not in_q:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if in_q:
        raise TemplateError(f"unterminated string in {expr!r}")
    parts.append("".join(buf).strip())
    return parts


def _lookup(path, context):
    cur = context
    for seg in path.split("."):
        if not seg:
            raise TemplateError(f"bad variable path {path!r}")
        if isinstance(cur, dict):
            cur = cur.get(seg, _MISSING)
        elif isinstance(cur, (list, tuple)) and re.fullmatch(r"-?\d+", seg):
            try:
                cur = cur[int(seg)]
            except IndexError:
                cur = _MISSING
        else:
            cur = getattr(cur, seg, _MISSING)
        if cur is _MISSING:
            return _MISSING
    return cur


def _evaluate(expr, context):
    parts = _split_filters(expr)
    path, filters = parts[0], parts[1:]
    if not path:
        raise TemplateError("empty expression")
    value = _lookup(path, context)
    has_default = any(_DEFAULT_RE.match(f) for f in filters)
    if value is _MISSING and not has_default:
        raise TemplateError(f"missing variable {path!r}")
    escape = True
    for f in filters:
        m = _DEFAULT_RE.match(f)
        if m:
            if value is _MISSING or value is None:
                value = m.group(1)
        elif f == "upper":
            value = _text(value).upper()
        elif f == "lower":
            value = _text(value).lower()
        elif f == "trim":
            value = _text(value).strip()
        elif f == "raw":
            escape = False
        else:
            raise TemplateError(f"unknown filter {f!r}")
    out = _text(value)
    return html.escape(out, quote=True) if escape else out


def _text(value):
    if value is None or value is _MISSING:
        return ""
    return str(value)


def render(template, context):
    out = []
    i, n = 0, len(template)
    while i < n:
        j = template.find("{{", i)
        if j == -1:
            out.append(template[i:])
            break
        if j > 0 and template[j - 1] == "\\":
            out.append(template[i:j - 1])
            out.append("{{")
            i = j + 2
            continue
        out.append(template[i:j])
        k = template.find("}}", j + 2)
        if k == -1:
            raise TemplateError("unclosed tag")
        out.append(_evaluate(template[j + 2:k].strip(), context))
        i = k + 2
    return "".join(out)
