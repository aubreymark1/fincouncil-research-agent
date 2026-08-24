"""The single public schema namespace for the research agent."""

from .claim import Claim
from .evidence import Evidence
from .industry import IndustryConfig, MetricRule, RiskRule
from .report import ResearchReport, RunMetadata
from .request import ResearchRequest
from .source import SourceDocument, TextChunk
from .validation import ValidationIssue

__all__ = [
    "Claim",
    "Evidence",
    "IndustryConfig",
    "MetricRule",
    "ResearchReport",
    "ResearchRequest",
    "RiskRule",
    "RunMetadata",
    "SourceDocument",
    "TextChunk",
    "ValidationIssue",
]
