"""YAML-based industry configuration loader.

C module responsibility: load ``configs/{industry_id}.yaml`` into the shared
``IndustryConfig`` schema. All failures carry a stable contract error code
(E200 for missing file, E201 for invalid YAML or schema violations).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.schemas import IndustryConfig

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


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
        This value must match the YAML file name and the file's
        ``industry_id`` field.

    Returns
    -------
    IndustryConfig
        The validated industry configuration.

    Raises
    ------
    IndustryConfigError
        With code ``E200`` when the file is missing, or ``E201`` when the
        YAML cannot be parsed or does not satisfy the public schema.
    """

    path = CONFIG_DIR / f"{industry_id}.yaml"
    if not path.is_file():
        raise IndustryConfigError(
            "E200",
            f"industry config file not found for industry_id={industry_id!r}",
            path=path,
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise IndustryConfigError(
            "E201",
            f"YAML parse error for industry_id={industry_id!r}: {exc}",
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

    return config
