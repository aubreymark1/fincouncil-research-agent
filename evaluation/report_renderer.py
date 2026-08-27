"""D-007 report rendering from structured experiment data.

The template lives in ``reports/template.md.j2``.  Renderers only read
structured files and the caller-supplied context; they never invent numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "reports" / "template.md.j2"


def render_report(
    template_path: str | Path,
    context: dict[str, Any],
    output_path: str | Path | None = None,
) -> str:
    """Render the Markdown report template.

    If ``output_path`` is given the rendered text is also written there.
    Returns the rendered Markdown string.
    """
    template_file = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(template_file.parent)),
        autoescape=select_autoescape(("html", "xml")),
        keep_trailing_newline=True,
    )
    template = env.get_template(template_file.name)
    rendered = template.render(**context)
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    return rendered
