"""Industry configuration and rule modules (C role)."""

from .loader import IndustryConfigError, load_industry_config

__all__ = ["IndustryConfigError", "load_industry_config"]
