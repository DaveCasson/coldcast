from __future__ import annotations

from typing import Any, Dict


class TemplateError(ValueError):
    pass


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        raise TemplateError(f"Missing template variable: {key}")


def render_template(template: str, context: Dict[str, Any]) -> str:
    try:
        return template.format_map(SafeDict(context))
    except KeyError as exc:
        raise TemplateError(str(exc)) from exc
