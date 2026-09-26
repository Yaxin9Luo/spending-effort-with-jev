"""Tiny static-site template engine with include support and a compile cache."""
from .errors import TemplateError, TemplateNotFound
from .renderer import Renderer
from .store import TemplateStore

__all__ = ["Renderer", "TemplateError", "TemplateNotFound", "TemplateStore"]
