"""Jinja2-backed rendering of a dictionary entry's presentation (BH-148).

Infrastructure boundary, mirroring ``infrastructure/ai_schema.py``: the Jinja2
engine and its sandbox are an external concern, so domain and application code
depend only on the ``EntryPresentationRenderer`` port, never on this module
(see ``packages/backend/AGENTS.md``).
"""

from collections.abc import Mapping
from typing import Any

from jinja2 import ChainableUndefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment

from cadmus.lexicography.domain import PresentationTemplateError


class Jinja2EntryPresentationRenderer:
    """Renders an ``ArticleSchema.presentation_formula`` against an assembled
    entry context, producing Markdown.

    The template author already holds ``Permission.EDIT`` on the dictionary, so
    the sandbox is a guard-rail against accidents (and obvious attribute-access
    escapes), not a multi-tenant trust boundary. ``ImmutableSandboxedEnvironment``
    also blocks mutation of the passed-in context. There is no loader, so
    ``{% include %}`` / ``{% import %}`` cannot reach the filesystem.
    """

    def __init__(self) -> None:
        self._env = ImmutableSandboxedEnvironment(
            autoescape=False,  # output is Markdown, not HTML
            undefined=ChainableUndefined,  # {{ a.b.c }} on a missing key -> ""
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_source: str, context: Mapping[str, Any]) -> str:
        try:
            template = self._env.from_string(template_source)
        except TemplateError as error:
            # TemplateSyntaxError on a malformed template.
            raise PresentationTemplateError(str(error)) from error
        try:
            return template.render(**context)
        except TemplateError as error:
            # UndefinedError / SecurityError from the rendered template.
            raise PresentationTemplateError(str(error)) from error
        except Exception as error:
            # A formula can still raise a plain Python error at render time
            # (e.g. ``{{ 1 / 0 }}``, a bad filter argument). The author holds
            # EDIT rights, not code access -- treat it as a template mistake,
            # never a 500.
            raise PresentationTemplateError(
                f"{type(error).__name__}: {error}"
            ) from error
