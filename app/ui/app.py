"""D-006 Streamlit page for research report review.

Run from the repository root:

    streamlit run app/ui/app.py

The page is read-only: it loads report.json, run_metadata.json and
metrics.json, then renders them.  It never calls a model and never writes
back to those files.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.ui.components import (
    claim_markdown,
    formal_claims,
    formal_risks,
    metric_rows,
    non_formal_claims,
)
from app.ui.data import (
    DEFAULT_METADATA_PATH,
    DEFAULT_REPORT_PATH,
    build_ui_model,
)
from app.ui.evidence_view import claim_evidence_markdown

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPORT = DEFAULT_REPORT_PATH
DEFAULT_METADATA = str(DEFAULT_METADATA_PATH) if DEFAULT_METADATA_PATH else ""


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    st.set_page_config(page_title="D-006 评测报告查看器", layout="wide")
    st.title("评测报告查看器")

    with st.sidebar:
        st.header("文件路径")
        report_value = st.text_input("report.json", value=str(DEFAULT_REPORT))
        metadata_value = st.text_input(
            "run_metadata.json（可选）", value=str(DEFAULT_METADATA)
        )
        metrics_value = st.text_input("metrics.json（可选）", value="")

    report_path = _resolve(report_value)
    metadata_path = _resolve(metadata_value) if metadata_value else None
    metrics_path = _resolve(metrics_value) if metrics_value else None

    try:
        model = build_ui_model(report_path, metadata_path, metrics_path)
    except Exception as exc:  # noqa: BLE001 - UI surfaces file errors to the user
        st.error(f"无法加载报告：{exc}")
        return

    report = model["report"]
    st.subheader(f"{report['company_name']} · {report['industry_id']}")
    st.write(f"Cutoff：{report['cutoff_date']}")
    st.write(f"Run ID：{report['run_id']}")

    if model["run_metadata"]:
        metadata = model["run_metadata"]
        st.caption(
            f"状态：{metadata.get('status', '')}；"
            f"模型：{metadata.get('model_provider', '')}/{metadata.get('model_name', '')}"
        )

    if model["metrics"]:
        st.markdown("### 指标")
        metrics_payload = model["metrics"]
        metric_values = metrics_payload.get("metrics", metrics_payload)
        if isinstance(metric_values, dict):
            for label, value in metric_rows(metric_values):
                st.write(f"- **{label}**：{value}")

    st.markdown("### 摘要")
    for line in report.get("summary", []):
        st.write(line)

    st.markdown("### 结论（正式）")
    for claim in formal_claims(report):
        st.markdown(claim_markdown(claim))
        with st.expander("查看证据"):
            st.markdown(claim_evidence_markdown(claim, report))

    st.markdown("### 风险（正式）")
    for risk in formal_risks(report):
        st.markdown(claim_markdown(risk))
        with st.expander("查看证据"):
            st.markdown(claim_evidence_markdown(risk, report))

    st.markdown("### 非正式结论 / 待人工确认")
    for claim in [*non_formal_claims(report), *report.get("unresolved_items", [])]:
        st.markdown(claim_markdown(claim))
        if claim.get("evidence_ids"):
            with st.expander("查看证据"):
                st.markdown(claim_evidence_markdown(claim, report))

    st.markdown("### 校验问题")
    for issue in report.get("validation_issues", []):
        st.write(f"- **{issue.get('severity', '')}** {issue.get('message', '')}")


if __name__ == "__main__":
    main()
