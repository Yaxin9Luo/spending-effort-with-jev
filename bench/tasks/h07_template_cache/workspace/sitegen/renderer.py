"""Compile and render templates.

Syntax:
    {{ name }}              value from the context, HTML-escaped; missing -> ""
    {% include "other" %}   the other template, inlined at compile time

Compiled templates are cached. Because includes are inlined when a template
is compiled, a compiled template depends on every template it includes,
directly or indirectly. When a template changes (or is deleted) in the store,
it and every template that currently includes it, directly or indirectly, are
dropped from the cache and recompiled on next use; everything else stays
cached. Each template is compiled at most once between changes that affect it.
"""
import html
import re

from .errors import TemplateError

_TOKEN = re.compile(r'\{\{\s*(\w+)\s*\}\}|\{%\s*include\s+"([^"]+)"\s*%\}')


class Renderer:
    def __init__(self, store):
        self.store = store
        self.compile_count = 0      # number of template compilations performed
        self._cache = {}            # name -> list of parts: ("text", str) | ("var", name)
        self._dependents = {}       # name -> set of templates that include it directly
        store.subscribe(self._on_change)

    # -- public -----------------------------------------------------------

    def render(self, name, context=None):
        context = context or {}
        out = []
        for kind, value in self._compiled(name, ()):
            if kind == "text":
                out.append(value)
            else:
                v = context.get(value)
                out.append("" if v is None else html.escape(str(v)))
        return "".join(out)

    def clear(self):
        self._cache.clear()
        self._dependents.clear()

    # -- cache ------------------------------------------------------------

    def _on_change(self, name):
        self._cache.pop(name, None)
        for parent in self._dependents.get(name, ()):
            self._cache.pop(parent, None)

    def _compiled(self, name, stack):
        if name in stack:
            chain = " -> ".join(stack + (name,))
            raise TemplateError(f"include cycle: {chain}")
        if name not in self._cache:
            self._cache[name] = self._compile(name, stack + (name,))
        return self._cache[name]

    def _compile(self, name, stack):
        source = self.store.get(name)
        self.compile_count += 1
        parts = []
        pos = 0
        for m in _TOKEN.finditer(source):
            if m.start() > pos:
                parts.append(("text", source[pos:m.start()]))
            var, include = m.groups()
            if var:
                parts.append(("var", var))
            else:
                self._dependents.setdefault(include, set()).add(name)
                parts.extend(self._compiled(include, stack))
            pos = m.end()
        if pos < len(source):
            parts.append(("text", source[pos:]))
        return parts
