"""Verified case catalog for the anonymous workbench.

The workbench only exposes two curated data packages that already exist in the
repository. It never accepts an arbitrary company as if source data had been
prepared.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.schemas import ResearchRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CUTOFF = date(2026, 8, 20)


@dataclass(frozen=True)
class WorkbenchCase:
    case_id: str
    display_name: str
    description: str
    request_template_path: Path
    default_cutoff: date
    supports_llm: bool


_CASES: tuple[WorkbenchCase, ...] = (
    WorkbenchCase(
        case_id="food_main",
        display_name="食品饮料行业样本",
        description=(
            "食品饮料行业公开财报与行业动态样本，包含贵州茅台、五粮液、伊利、"
            "海天、汾酒、泸州老窖等公司资料。"
        ),
        request_template_path=PROJECT_ROOT / "fixtures" / "shared" / "research_request.json",
        default_cutoff=DEFAULT_CUTOFF,
        supports_llm=True,
    ),
    WorkbenchCase(
        case_id="bank_main",
        display_name="中国工商银行样本",
        description=(
            "银行行业公开财报样本，以中国工商银行为主，包含平安银行、兴业银行、"
            "农业银行等公司资料。"
        ),
        request_template_path=PROJECT_ROOT / "fixtures" / "shared" / "bank_request.json",
        default_cutoff=DEFAULT_CUTOFF,
        supports_llm=True,
    ),
)


def list_workbench_cases() -> tuple[WorkbenchCase, ...]:
    """Return the two verified research packages."""
    return _CASES


def get_workbench_case(case_id: str) -> WorkbenchCase:
    """Return one verified case or raise a coded ValueError."""
    for case in _CASES:
        if case.case_id == case_id:
            return case
    raise ValueError(
        f"E500 module=workbench.cases: unknown case_id {case_id!r}; "
        "current anonymous workbench only supports food_main and bank_main"
    )


def build_workbench_request(
    case_id: str,
    cutoff_date: date,
    run_id: str,
    *,
    outputs_dir: Path | None = None,
) -> ResearchRequest:
    """Build a ResearchRequest for one verified case.

    The output directory is always unique per run and remains below an
    ``outputs`` directory so the existing pipeline validation is satisfied.
    """
    case = get_workbench_case(case_id)
    payload = json.loads(case.request_template_path.read_text(encoding="utf-8"))
    request = ResearchRequest.model_validate(payload)

    if outputs_dir is None:
        outputs_dir = PROJECT_ROOT / "outputs"
    output_dir = outputs_dir / "reports" / run_id
    if "outputs" not in {part.lower() for part in output_dir.parts}:
        raise ValueError(
            f"E500 module=workbench.cases: outputs_dir must be below an outputs directory: {outputs_dir}"
        )

    return request.model_copy(
        update={
            "run_id": run_id,
            "company_name": case.display_name,
            "cutoff_date": cutoff_date,
            "output_dir": str(output_dir),
        }
    )
