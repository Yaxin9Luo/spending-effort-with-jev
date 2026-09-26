"""In-memory template storage with change notifications (the dev server's file watcher writes here)."""
from .errors import TemplateNotFound


class TemplateStore:
    def __init__(self, templates=None):
        self._templates = dict(templates or {})
        self._listeners = []

    def subscribe(self, callback):
        """Call `callback(name)` whenever a template is set or deleted."""
        self._listeners.append(callback)

    def get(self, name):
        try:
            return self._templates[name]
        except KeyError:
            raise TemplateNotFound(name) from None

    def names(self):
        return sorted(self._templates)

    def set(self, name, text):
        self._templates[name] = text
        self._notify(name)

    def delete(self, name):
        if name not in self._templates:
            raise TemplateNotFound(name)
        del self._templates[name]
        self._notify(name)

    def _notify(self, name):
        for cb in list(self._listeners):
            cb(name)
