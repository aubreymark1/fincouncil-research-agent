"""YAML-based industry configuration loader.

C module responsibility: load ``configs/{industry_id}.yaml`` into the shared
``IndustryConfig`` schema. All failures carry a stable contract error code
(E200 for missing file, E201 for invalid YAML or schema violations).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.schemas import IndustryConfig

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
INDUSTRY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class IndustryConfigError(RuntimeError):
    """Raised when an industry configuration cannot be loaded."""

    def __init__(self, code: str, message: str, path: Path | None = None) -> None:
        self.code = code
        self.path = str(path) if path is not None else None
        detail = f"{code} module=industry.loader: {message}"
        if self.path:
            detail += f" path={self.path}"
        super().__init__(detail)


def load_industry_config(industry_id: str) -> IndustryConfig:
    """Load and validate the YAML configuration for ``industry_id``.

    Parameters
    ----------
    industry_id:
        Stable industry identifier, e.g. ``food_beverage`` or ``banking``.
        Must match ``^[A-Za-z0-9_-]+$`` and the YAML file's ``industry_id``.

    Returns
    -------
    IndustryConfig
        The validated industry configuration.

    Raises
    ------
    IndustryConfigError
        With code ``E200`` when the file is missing, or ``E201`` when the
        identifier is unsafe, the YAML cannot be parsed, the file cannot be
        read, or the content does not satisfy the public schema.
    """

    if not isinstance(industry_id, str) or not INDUSTRY_ID_PATTERN.fullmatch(industry_id):
        raise IndustryConfigError(
            "E201",
            (
                f"invalid industry_id={industry_id!r}; "
                "expected stable identifier matching ^[A-Za-z0-9_-]+$"
            ),
        )

    path = CONFIG_DIR / f"{industry_id}.yaml"
    resolved_path = path.resolve()
    if resolved_path.parent != CONFIG_DIR.resolve():
        raise IndustryConfigError(
            "E201",
            f"industry config path escapes configs directory: {resolved_path}",
            path=path,
        )

    if not resolved_path.is_file():
        raise IndustryConfigError(
            "E200",
            f"industry config file not found for industry_id={industry_id!r}",
            path=path,
        )

    try:
        raw = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        raise IndustryConfigError(
            "E201",
            f"cannot read or parse YAML for industry_id={industry_id!r}: {exc}",
            path=path,
        ) from exc

    if not isinstance(raw, dict):
        raise IndustryConfigError(
            "E201",
            f"industry config must be a YAML mapping, got {type(raw).__name__}",
            path=path,
        )

    try:
        config = IndustryConfig.model_validate(raw)
    except ValidationError as exc:
        raise IndustryConfigError(
            "E201",
            f"industry config failed schema validation for industry_id={industry_id!r}: {exc}",
            path=path,
        ) from exc

    if config.industry_id != industry_id:
        raise IndustryConfigError(
            "E201",
            (
                f"industry_id mismatch: requested={industry_id!r} "
                f"but config declares {config.industry_id!r}"
            ),
            path=path,
        )

    _validate_metric_keywords(config, path=path)
    return config


def _validate_metric_keywords(config: IndustryConfig, path: Path) -> None:
    """Reject MetricRule keywords that are empty or contain only whitespace.

    The public schema still allows empty keyword lists, but empty keywords
    would make coverage checks match every Evidence. The loader therefore
    enforces the stricter requirement before returning a config.
    """

    for metric in config.required_metrics:
        if not metric.keywords:
            raise IndustryConfigError(
                "E201",
                (
                    f"metric {metric.metric_id} ({metric.display_name}) "
                    "must define at least one keyword"
                ),
                path=path,
            )
        blank_keywords = [keyword for keyword in metric.keywords if not keyword.strip()]
        if blank_keywords:
            raise IndustryConfigError(
                "E201",
                (
                    f"metric {metric.metric_id} ({metric.display_name}) "
                    f"has blank keyword entries: {blank_keywords!r}"
                ),
                path=path,
            )
