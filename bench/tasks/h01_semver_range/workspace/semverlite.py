"""Semver helpers for the internal package index.

The index has to resolve dependency ranges written for npm, so range
evaluation must agree with what npm itself would pick.
"""


def satisfies(version, range_):
    """Return True if `version` (a string) satisfies `range_` (a string)."""
    raise NotImplementedError


def max_satisfying(versions, range_):
    """Return the highest version string in `versions` that satisfies `range_`, or None."""
    raise NotImplementedError
