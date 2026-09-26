"""Apply JSON Patch documents to parsed JSON values.

Used by the config service: clients send a patch, we apply it to the
stored document (already parsed with json.loads) and store the result.
"""


class JsonPatchError(Exception):
    """Raised when a patch cannot be applied."""


def apply_patch(doc, patch):
    """Apply `patch` (a list of operation dicts) to `doc` and return the result."""
    raise NotImplementedError
