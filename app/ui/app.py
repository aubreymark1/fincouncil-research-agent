"""FINAL-001 Streamlit page for report and experiment review.

Run from the repository root:

    streamlit run app/ui/app.py

The page is read-only: it loads report.json, report.md, run_metadata.json,
metrics.json and optional results.json/csv, then renders them. It never calls
a model and never writes back to those files.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

import streamlit as st
import streamlit.components.v1 as streamlit_components

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT_STRING = str(PROJECT_ROOT)
if PROJECT_ROOT_STRING in sys.path:
    sys.path.remove(PROJECT_ROOT_STRING)
sys.path.insert(0, PROJECT_ROOT_STRING)

from app.ui.components import (
    claim_markdown,
    experiment_status_message,
    formal_claims,
    formal_risks,
    metric_rows,
    non_formal_claims,
)
from app.ui.data import (
    DEFAULT_METADATA_PATH,
    DEFAULT_REPORT_PATH,
    load_ui_model,
    report_export_payloads,
)
from app.ui.evidence_view import claim_evidence_markdown
from evaluation.charts import generate_charts

DEFAULT_REPORT = DEFAULT_REPORT_PATH
DEFAULT_METADATA = str(DEFAULT_METADATA_PATH) if DEFAULT_METADATA_PATH else ""


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    st.set_page_config(page_title="FINAL-001 报告工作台", layout="wide")
    st.title("FINAL-001 报告工作台")

    with st.sidebar:
        st.header("文件路径")
        report_value = st.text_input("report.json", value=str(DEFAULT_REPORT))
        markdown_value = st.text_input("report.md（可选）", value="")
        metadata_value = st.text_input(
            "run_metadata.json（可选）", value=str(DEFAULT_METADATA)
        )
        metrics_value = st.text_input("metrics.json（可选）", value="")
        results_value = st.text_input("results.json/csv（可选）", value="")

    report_path = _resolve(report_value)
    markdown_path = _resolve(markdown_value) if markdown_value else None
    metadata_path = _resolve(metadata_value) if metadata_value else None
    metrics_path = _resolve(metrics_value) if metrics_value else None
    results_path = _resolve(results_value) if results_value else None

    model = load_ui_model(
        report_path,
        metadata_path,
        metrics_path,
        report_markdown_path=markdown_path,
        results_path=results_path,
    )
    _render_file_status(model)
    _render_run_status(model)

    report = model["report"]
    if report is None:
        st.error("report.json 不可用，无法展示报告正文；请检查文件状态和运行错误。")
        _render_experiment_results(model)
        return

    st.subheader(f"{report['company_name']} · {report['industry_id']}")
    st.write(f"Cutoff：{report['cutoff_date']}　·　Run ID：{report['run_id']}")

    _render_report_markdown(model)
    _render_metrics(model)

    _render_experiment_results(model)

    st.markdown("### 摘要")
    if report.get("summary"):
        for line in report["summary"]:
            st.write(f"- {line}")
    else:
        st.info("报告未提供摘要。")

    st.markdown("### 结论（正式）")
    _render_claims(formal_claims(report), report, "正式结论")

    st.markdown("### 风险（正式）")
    _render_claims(formal_risks(report), report, "正式风险")

    st.markdown("### 待人工确认 / 未决项")
    _render_claims(
        [*non_formal_claims(report), *report.get("unresolved_items", [])],
        report,
        "待确认项",
    )

    _render_evidence_index(report)

    st.markdown("### 校验问题")
    _render_validation_issues(report)
    _render_report_exports(model)


def _render_file_status(model: dict) -> None:
    statuses = model.get("file_status", {})
    if not statuses:
        return
    for name, artifact in statuses.items():
        status = artifact.get("status")
        if status == "missing":
            st.warning(f"缺少 {name}：{artifact.get('path', '')}")
        elif status == "invalid":
            st.error(f"无法读取 {name}：{artifact.get('message', '')}")


def _render_run_status(model: dict) -> None:
    metadata = model.get("run_metadata")
    if not isinstance(metadata, dict):
        return
    status = metadata.get("status", "unknown")
    st.caption(
        f"运行状态：{status}；模型：{metadata.get('model_provider', '')}/"
        f"{metadata.get('model_name', '')}"
    )
    if status == "failed":
        st.error("本次运行失败，以下错误来自 run_metadata.json：")
    elif status == "partial":
        st.warning("本次运行仅部分完成，结论不能视为完整结果。")
    elif status == "running":
        st.info("本次运行仍在进行，报告内容可能不完整。")
    for error in metadata.get("errors") or []:
        st.code(str(error))


def _render_report_markdown(model: dict) -> None:
    markdown = model.get("report_markdown")
    if markdown is None:
        return
    with st.expander("查看原始 report.md（只读）"):
        st.code(markdown, language="markdown")


def _render_metrics(model: dict) -> None:
    st.markdown("### 指标（来自 metrics.json）")
    metrics_payload = model.get("metrics")
    if not isinstance(metrics_payload, dict):
        st.info("未加载 metrics.json；页面不会根据 Gold 或报告临时计算实验分数。")
        return
    metrics_status = metrics_payload.get("status")
    if metrics_status == "disabled":
        st.info("metrics.json 标记为 disabled，当前实验未运行。")
        return
    if metrics_status == "failed":
        st.warning("metrics.json 对应运行失败，未提供可展示的指标。")
        return
    values = metrics_payload.get("metrics", metrics_payload)
    rows = metric_rows(values) if isinstance(values, dict) else []
    if not rows:
        st.info("metrics.json 未提供可展示的指标。")
        return
    st.caption("仅展示已存在于 metrics.json 的数值；页面不会生成新的正式评分。")
    for label, value in rows:
        st.write(f"- **{label}**：{value}")


def _render_experiment_results(model: dict) -> None:
    st.markdown("### 实验结果与图表（来自 results.json/csv）")
    rows = model.get("experiment_rows") or []
    if not rows:
        st.info("未加载 results.json/csv；disabled、failed 和无数据不会被绘成 0。")
        return
    st.dataframe(
        [
            {
                "实验": row.get("experiment_id", ""),
                "名称": row.get("name", ""),
                "状态": row.get("status", ""),
                "错误": row.get("error") or "",
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )
    for row in rows:
        status = row.get("status")
        message = experiment_status_message(row)
        if status == "disabled":
            st.info(message)
        elif status == "failed":
            st.warning(message)
        elif status == "running":
            st.info(message)
    _render_result_charts(model)


def _render_result_charts(model: dict) -> None:
    artifact = model.get("file_status", {}).get("results", {})
    if artifact.get("status") != "loaded":
        return
    results_path = artifact.get("path")
    if not results_path:
        return
    try:
        with tempfile.TemporaryDirectory(prefix="final-001-charts-") as chart_dir:
            chart_paths = generate_charts(results_path, chart_dir)
            for chart_path in chart_paths:
                st.caption(chart_path.name)
                streamlit_components.html(
                    chart_path.read_text(encoding="utf-8"),
                    height=380,
                    scrolling=False,
                )
    except Exception as exc:  # noqa: BLE001 - UI surfaces chart input errors
        st.error(f"无法从 results 文件生成图表：{exc}")


def _render_claims(claims: list[dict], report: dict, label: str) -> None:
    if not claims:
        st.info(f"没有{label}。")
        return
    for claim in claims:
        st.markdown(claim_markdown(claim))
        if claim.get("evidence_ids"):
            with st.expander(f"查看 {label}证据 · {claim.get('claim_id', '')}"):
                st.markdown(claim_evidence_markdown(claim, report))


def _render_evidence_index(report: dict) -> None:
    st.markdown("### Evidence 索引（只读）")
    evidence = report.get("evidence_index", [])
    if not evidence:
        st.info("报告没有 Evidence 索引。")
        return
    st.caption(f"共 {len(evidence)} 条；详细原文在结论/风险的证据展开项中查看。")
    st.dataframe(
        [
            {
                "evidence_id": item.get("evidence_id", ""),
                "doc_id": item.get("doc_id", ""),
                "published_at": item.get("published_at", ""),
                "page": item.get("page", ""),
                "review_status": item.get("review_status", ""),
                "locator": item.get("locator", ""),
            }
            for item in evidence
        ],
        width="stretch",
        hide_index=True,
    )


def _render_validation_issues(report: dict) -> None:
    issues = report.get("validation_issues", [])
    if not issues:
        st.info("没有 ValidationIssue。")
        return
    for issue in issues:
        st.write(
            f"- **{issue.get('severity', '')}** "
            f"`{issue.get('issue_id', '')}` {issue.get('message', '')}"
        )


def _render_report_exports(model: dict) -> None:
    exports = report_export_payloads(model)
    if not exports:
        return
    st.markdown("### 报告导出")
    for filename, payload in exports.items():
        mime = "application/json" if filename.endswith(".json") else "text/markdown"
        st.download_button(
            label=f"下载 {filename}",
            data=payload,
            file_name=filename,
            mime=mime,
            key=f"download-{filename}",
        )


if __name__ == "__main__":
    main()
