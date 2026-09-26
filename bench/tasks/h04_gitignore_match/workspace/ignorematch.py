"""Decide which files the bundler should skip, using the repo's .gitignore."""


def is_ignored(path, patterns, is_dir=False):
    """Return True if git would ignore `path`.

    path     -- path relative to the repository root, '/'-separated, no leading './'
    patterns -- the lines of the repository's top-level .gitignore
    is_dir   -- True if `path` itself is a directory
    """
    raise NotImplementedError
