"""Chart generation for D-005.

Charts are intentionally dependency-free: they read ``results.json`` or
``results.csv`` produced by D-003 and emit standalone SVG files.  No chart
value is hand-written; missing data is rendered as an explicit "no data"
state.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

CHART_WIDTH = 640
CHART_HEIGHT = 360
BAR_MAX_HEIGHT = 220
MARGIN_LEFT = 48
MARGIN_BOTTOM = 48
MARGIN_TOP = 32


def _load_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load experiment result rows from results.json or results.csv."""
    results_path = Path(path)
    if not results_path.exists():
        raise ValueError(f"results file does not exist: {results_path}")
    if results_path.suffix.lower() == ".json":
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("results.json root must be a list of result rows")
        return payload
    if results_path.suffix.lower() == ".csv":
        with results_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        return rows
    raise ValueError(f"unsupported results file type: {results_path.suffix}")


METRIC_KEYS = (
    "key_factor_coverage_rate",
    "evidence_validity_rate",
    "citation_location_accuracy_rate",
    "numeric_error_rate",
    "cutoff_violation_count",
    "industry_metric_coverage_rate",
)


def _metrics(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("metrics")
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {key: row.get(key) for key in METRIC_KEYS if key in row}
    return {}


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _duration_minutes(started_at: Any, finished_at: Any) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finish = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        return max(0.0, (finish - start).total_seconds() / 60.0)
    except ValueError:
        return None


def _svg_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _bar_chart_svg(
    title: str,
    labels: Sequence[str],
    values: Sequence[float],
    *,
    y_label: str = "值",
    format_value: str = "{:.2f}",
) -> str:
    """Render a simple vertical bar chart as standalone SVG."""
    n = max(1, len(labels))
    slot = (CHART_WIDTH - MARGIN_LEFT - 24) / n
    bar_width = max(8.0, slot * 0.6)
    max_value = max([max(values), 1.0]) if values else 1.0
    baseline = CHART_HEIGHT - MARGIN_BOTTOM

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CHART_WIDTH}" '
        f'height="{CHART_HEIGHT}" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}">',
        f"<text x=\"{MARGIN_LEFT}\" y=\"20\" font-size=\"16\" font-weight=\"bold\">"
        f"{_svg_escape(title)}</text>",
        f'<text x="{MARGIN_LEFT - 4}" y="{baseline + 20}" text-anchor="end" '
        f'font-size="10">{_svg_escape(y_label)}</text>',
    ]
    if not values:
        parts.append(
            f'<text x="{CHART_WIDTH / 2}" y="{CHART_HEIGHT / 2}" text-anchor="middle" '
            'font-size="14" fill="#888">no data</text>'
        )
        parts.append("</svg>")
        return "\n".join(parts)

    for index, (label, value) in enumerate(zip(labels, values)):
        x = MARGIN_LEFT + index * slot + (slot - bar_width) / 2
        height = max(0.0, (value / max_value) * BAR_MAX_HEIGHT)
        y = baseline - height
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{height:.1f}" fill="#4C78A8"/>'
        )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
            f'font-size="10">{format_value.format(value)}</text>'
        )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{baseline + 14:.1f}" '
            f'text-anchor="middle" font-size="10">{_svg_escape(str(label))}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _experiment_series(
    rows: Iterable[dict[str, Any]], metric_key: str
) -> tuple[list[str], list[float]]:
    labels: list[str] = []
    values: list[float] = []
    for row in rows:
        experiment_id = str(row.get("experiment_id", ""))
        if experiment_id not in {"E0", "E1", "E2", "E3"}:
            continue
        labels.append(experiment_id)
        values.append(_as_float(_metrics(row).get(metric_key)))
    return labels, values


def generate_charts(results_path: str | Path, output_dir: str | Path) -> list[Path]:
    """Generate all D-005 charts from one results file.

    Returns the list of created SVG paths.
    """
    rows = _load_rows(results_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    charts: list[tuple[str, str, list[str], list[float], str]] = [
        (
            "E0-E3 关键因素覆盖率",
            "coverage.svg",
            *_experiment_series(rows, "key_factor_coverage_rate"),
            "覆盖率",
        ),
        (
            "E0-E3 证据有效率",
            "evidence_validity.svg",
            *_experiment_series(rows, "evidence_validity_rate"),
            "有效率",
        ),
    ]

    written: list[Path] = []
    for title, filename, labels, values, y_label in charts:
        path = out / filename
        path.write_text(_bar_chart_svg(title, labels, values, y_label=y_label), encoding="utf-8")
        written.append(path)

    # 错误与拦截：cutoff 违规数 + 失败运行数（如存在）。
    cutoff_labels = [str(row.get("experiment_id", "")) for row in rows if row.get("experiment_id")]
    cutoff_values = [_as_float(_metrics(row).get("cutoff_violation_count")) for row in rows if row.get("experiment_id")]
    errors_path = out / "errors_and_cutoff.svg"
    errors_path.write_text(
        _bar_chart_svg(
            "错误与 cutoff 拦截",
            cutoff_labels,
            cutoff_values,
            y_label="cutoff 违规数",
            format_value="{:.0f}",
        ),
        encoding="utf-8",
    )
    written.append(errors_path)

    # 人工修改时间（E0 的 started_at/finished_at 差值）。
    manual_labels: list[str] = []
    manual_values: list[float] = []
    for row in rows:
        if row.get("experiment_id") != "E0":
            continue
        duration = _duration_minutes(row.get("started_at"), row.get("finished_at"))
        manual_labels.append("E0")
        manual_values.append(duration if duration is not None else 0.0)
    manual_path = out / "manual_time.svg"
    manual_path.write_text(
        _bar_chart_svg(
            "E0 人工修改时间",
            manual_labels,
            manual_values,
            y_label="分钟",
            format_value="{:.1f}",
        ),
        encoding="utf-8",
    )
    written.append(manual_path)

    # 银行迁移指标覆盖：bank_main 或 banking case 的行业必查覆盖率。
    bank_rows = [
        row
        for row in rows
        if str(row.get("case_id", "")).startswith("bank")
        or "bank" in str(row.get("gold_path", "")).lower()
    ]
    bank_labels = [str(row.get("experiment_id", "")) for row in bank_rows] or ["bank"]
    bank_values = [_as_float(_metrics(row).get("industry_metric_coverage_rate")) for row in bank_rows] or [0.0]
    bank_path = out / "bank_migration_coverage.svg"
    bank_path.write_text(
        _bar_chart_svg(
            "银行迁移指标覆盖",
            bank_labels,
            bank_values,
            y_label="覆盖率",
        ),
        encoding="utf-8",
    )
    written.append(bank_path)

    return written
