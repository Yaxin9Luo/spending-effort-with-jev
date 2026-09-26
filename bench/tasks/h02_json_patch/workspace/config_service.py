"""Minimal in-memory config store that accepts JSON Patch updates."""
import json

from jsonpatch_lite import JsonPatchError, apply_patch


class ConfigStore:
    def __init__(self):
        self._docs = {}

    def put(self, name, text):
        self._docs[name] = json.loads(text)

    def get(self, name):
        return self._docs[name]

    def patch(self, name, patch_text):
        """Apply a JSON Patch (as JSON text). Returns True on success, False if rejected."""
        try:
            self._docs[name] = apply_patch(self._docs[name], json.loads(patch_text))
        except JsonPatchError:
            return False
        return True
