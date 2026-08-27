"""Evidence-bound analysis nodes, Critic, and report renderer."""

from .aggregation import run_analysis
from .critic import run_critic
from .fundamental import analyze_fundamentals
from .news_policy import analyze_news_policy
from .report import render_markdown, render_report
from .risk import analyze_risks

__all__ = [
    "analyze_fundamentals",
    "analyze_news_policy",
    "analyze_risks",
    "render_markdown",
    "render_report",
    "run_analysis",
    "run_critic",
]
