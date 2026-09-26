class TemplateError(Exception):
    """Problem with a template (bad syntax, include cycle, ...)."""


class TemplateNotFound(TemplateError):
    """A template (or an included template) does not exist."""
