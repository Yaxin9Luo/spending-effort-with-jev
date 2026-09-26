"""Tiny template renderer for notification emails."""


class TemplateError(Exception):
    pass


def render(template, context):
    raise NotImplementedError
