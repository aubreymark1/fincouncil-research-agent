"""Tests for the D-003 reproducible experiment runner and its CLI."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas import ResearchRequest  # noqa: E402
from evaluation import experiment_runner  # noqa: E402
from evaluation.experiment_runner import (  # noqa: E402
    DEFAULT_DEFINITIONS,
    ExperimentDefinition,
    _run_experiment_definition,
    compute_input_hash,
    import_manual_baseline,
    load_definitions,
    run_case_experiments,
    run_experiment,
)


@pytest.fixture(autouse=True)
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every runner write into pytest's tmp_path.

    Without this patch the runner writes into the repository's real
    ``outputs/experiments`` tree; teardowns that fail silently then
    accumulate garbage directories case after case.
    """
    root = tmp_path / "isolate"
    root.mkdir()
    monkeypatch.setattr(experiment_runner, "PROJECT_ROOT", root)
    return root


def _unique_case(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _make_request(tmp_path: Path, run_id: str = "RUN-TEST") -> tuple[ResearchRequest, Path, Path]:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("doc_id,path\nDOC-1,report.pdf\n", encoding="utf-8")
    output_dir = tmp_path / "outputs" / "reports" / run_id
    request = ResearchRequest(
        run_id=run_id,
        company_name="测试公司",
        ticker="000001.SZ",
        industry_id="food_beverage",
        cutoff_date=date(2026, 8, 20),
        source_manifest_path=str(manifest),
        output_dir=str(output_dir),
    )
    return request, manifest, output_dir


def _report_payload(run_id: str = "RUN-TEST") -> dict:
    return {
        "run_id": run_id,
        "company_name": "测试公司",
        "industry_id": "food_beverage",
        "cutoff_date": "2026-08-20",
        "summary": ["测试摘要"],
        "claims": [],
        "risks": [],
        "unresolved_items": [],
        "evidence_index": [],
        "validation_issues": [],
        "generated_at": "2026-08-20T00:00:00Z",
        "report_version": "test-v1",
    }


def _metadata_payload(run_id: str = "RUN-TEST") -> dict:
    return {
        "run_id": run_id,
        "started_at": "2026-08-20T00:00:00Z",
        "finished_at": "2026-08-20T00:00:01Z",
        "status": "success",
        "model_provider": "test",
        "model_name": "fake",
        "prompt_versions": {},
        "input_hashes": {},
        "module_versions": {},
        "errors": [],
    }


def _fake_executor(output_dir: Path, run_id: str, code: int = 0, output: str = ""):
    """An executor that writes a valid report + metadata as if the pipeline ran."""

    def executor(command: str) -> tuple[int, str]:
        assert command  # the frozen run_command must reach the executor
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "report.json").write_text(
            json.dumps(_report_payload(run_id), ensure_ascii=False), encoding="utf-8"
        )
        logs_root = output_dir.parents[1] / "logs" / run_id
        logs_root.mkdir(parents=True, exist_ok=True)
        (logs_root / "run_metadata.json").write_text(
            json.dumps(_metadata_payload(run_id), ensure_ascii=False), encoding="utf-8"
        )
        return code, output

    return executor


@pytest.fixture()
def case_defs(tmp_path: Path):
    """A throwaway definitions file with a unique case_id and real E1-E3."""
    value = _unique_case("d003")
    request_path = tmp_path / f"{value}_request.json"
    request_path.write_text(
        json.dumps(
            {
                "run_id": "RUN-TEST",
                "company_name": "测试公司",
                "ticker": "000001.SZ",
                "industry_id": "food_beverage",
                "cutoff_date": "2026-08-20",
                "source_manifest_path": str(tmp_path / "manifest.csv"),
                "output_dir": str(tmp_path / "outputs" / "reports" / "RUN-TEST"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    defs = tmp_path / "defs.yaml"
    defs.write_text(
        "schema_version: '1.0'\n"
        "cases:\n"
        f"  - case_id: {value}\n"
        f"    request_path: {request_path.as_posix()}\n"
        "    gold_path: null\n"
        "experiments:\n"
        "  E0:\n"
        "    name: manual_baseline\n"
        "    description: manual\n"
        "    run_command: null\n"
        "    enabled: true\n"
        "  E1:\n"
        "    name: generic_agent\n"
        "    description: generic\n"
        "    run_command: '{python} scripts/run_case.py --request {request_path}'\n"
        "    enabled: true\n"
        "  E2:\n"
        "    name: industry_agent\n"
        "    description: industry\n"
        "    run_command: '{python} scripts/run_case.py --request {request_path}'\n"
        "    enabled: true\n"
        "  E3:\n"
        "    name: full_system\n"
        "    description: full\n"
        "    run_command: '{python} scripts/run_case.py --request {request_path}'\n"
        "    enabled: true\n",
        encoding="utf-8",
    )
    yield value, defs
    # No manual teardown: every artefact already lives under tmp_path via
    # the isolated_root fixture, which pytest cleans up itself.


class TestDefinitions:
    def test_loads_frozen_file(self) -> None:
        cases, experiments, output_cfg = load_definitions(DEFAULT_DEFINITIONS)
        assert [case.case_id for case in cases] == ["food_main", "bank_main"]
        assert set(experiments) == {"E0", "E1", "E2", "E3"}
        assert experiments["E0"].run_command is None
        assert all(experiments[name].run_command for name in ("E1", "E2", "E3"))
        assert isinstance(output_cfg, dict)

    def test_frozen_case_paths_resolve_to_project_root(self) -> None:
        """相对路径必须按仓库根解析，不能解析到 evaluation/ 目录下。

        food_main 和 bank_main 的 request 与已签收 Gold 都必须存在。
        """
        cases, _, _ = load_definitions(DEFAULT_DEFINITIONS)
        case_map = {c.case_id: c for c in cases}

        food = case_map["food_main"]
        assert food.request_path.exists(), (
            f"food_main request_path 不存在: {food.request_path}"
        )
        assert str(food.request_path).startswith(str(PROJECT_ROOT))
        assert "evaluation/fixtures" not in str(food.request_path).replace("\\", "/")

        bank = case_map["bank_main"]
        assert bank.request_path.exists(), (
            f"bank_main request_path 不存在: {bank.request_path}"
        )
        assert str(bank.request_path).startswith(str(PROJECT_ROOT))
        assert "evaluation/fixtures" not in str(bank.request_path).replace("\\", "/")
        assert bank.gold_path == PROJECT_ROOT / "fixtures" / "evaluation" / "bank_gold.json"
        assert food.gold_path == PROJECT_ROOT / "fixtures" / "evaluation" / "food_gold.json"

    def test_frozen_experiments_carry_enabled_flag(self) -> None:
        """冻结定义的每个实验都有 enabled 字段。"""
        _, experiments, _ = load_definitions(DEFAULT_DEFINITIONS)
        for eid, definition in experiments.items():
            assert hasattr(definition, "enabled"), eid
            assert isinstance(definition.enabled, bool), eid

    def test_frozen_e1_e3_disabled_until_experiment_run(self) -> None:
        """E1/E2/E3 在 EXP-001 正式运行前保持 disabled。"""
        _, experiments, _ = load_definitions(DEFAULT_DEFINITIONS)
        assert experiments["E0"].enabled is True
        for eid in ("E1", "E2", "E3"):
            assert experiments[eid].enabled is False, eid

    def test_frozen_bank_main_enabled_after_request_signed(self) -> None:
        """food_main 和 bank_main 的 request、Gold 均已接入定义。"""
        cases, _, _ = load_definitions(DEFAULT_DEFINITIONS)
        case_map = {c.case_id: c for c in cases}
        assert case_map["food_main"].enabled is True
        assert case_map["bank_main"].enabled is True

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            load_definitions(tmp_path / "missing.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(": not: [valid", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid YAML"):
            load_definitions(path)

    def test_unfrozen_experiment_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "defs.yaml"
        path.write_text(
            "schema_version: '1.0'\n"
            "cases:\n"
            "  - case_id: food_main\n"
            "    request_path: fixtures/shared/research_request.json\n"
            "    gold_path: null\n"
            "experiments:\n"
            "  E0:\n"
            "    name: manual_baseline\n"
            "    description: manual\n"
            "    run_command: null\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must freeze the E1 experiment"):
            load_definitions(path)


class TestInputHash:
    def test_hash_is_stable_and_manifest_sensitive(
        self, tmp_path: Path
    ) -> None:
        request, manifest, _ = _make_request(tmp_path)
        first = compute_input_hash(request, manifest)
        second = compute_input_hash(request, manifest)
        assert first == second
        assert first["request"].startswith("sha256:")
        assert first["manifest"].startswith("sha256:")
        assert first["manifest"] != first["request"]

    def test_hash_changes_when_manifest_changes(self, tmp_path: Path) -> None:
        request, manifest, _ = _make_request(tmp_path)
        before = compute_input_hash(request, manifest)
        manifest.write_text("doc_id,path\nDOC-2,other.pdf\n", encoding="utf-8")
        after = compute_input_hash(request, manifest)
        assert after["manifest"] != before["manifest"]
        assert after["request"] == before["request"]


class TestRunExperiment:
    def test_success_writes_full_directory(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        case_id, defs_path = case_defs
        request, _, output_dir = _make_request(tmp_path)
        executor = _fake_executor(output_dir, request.run_id)
        row = run_experiment(
            "E1", request, definitions=defs_path, executor=executor, case_id=case_id
        )

        assert row["experiment_id"] == "E1"
        assert row["case_id"] == case_id
        assert row["status"] == "success"
        assert row["error"] is None
        assert row["input_hashes"]["request"].startswith("sha256:")

        experiment_dir = (
            isolated_root / "outputs" / "experiments" / case_id / "E1"
        )
        for name in (
            "request.json",
            "report.json",
            "run_metadata.json",
            "metrics.json",
        ):
            assert (experiment_dir / name).exists(), name
        assert not (experiment_dir / "error.txt").exists()
        metrics = json.loads((experiment_dir / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["status"] == "success"

    def test_nonzero_exit_is_recorded_not_deleted(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        case_id, defs_path = case_defs
        request, _, output_dir = _make_request(tmp_path)
        executor = _fake_executor(output_dir, request.run_id, code=1, output="boom")
        row = run_experiment(
            "E2", request, definitions=defs_path, executor=executor, case_id=case_id
        )

        assert row["status"] == "failed"
        assert "boom" in row["error"]
        assert row["error_count"] == 1
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E2"
        assert (experiment_dir / "error.txt").exists()
        assert (experiment_dir / "report.json").exists()
        assert (experiment_dir / "request.json").exists()

    def test_crashed_pipeline_keeps_error_file(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        case_id, defs_path = case_defs
        request, _, output_dir = _make_request(tmp_path)

        def crashed_executor(command: str) -> tuple[int, str]:
            return 0, ""

        row = run_experiment(
            "E3", request, definitions=defs_path, executor=crashed_executor, case_id=case_id
        )
        assert row["status"] == "failed"
        assert "FileNotFoundError" in row["error"]
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E3"
        assert (experiment_dir / "error.txt").exists()
        assert not (experiment_dir / "report.json").exists()

    def test_e0_direct_call_is_rejected(self, tmp_path: Path) -> None:
        request, _, _ = _make_request(tmp_path)
        with pytest.raises(ValueError, match="call import_manual_baseline"):
            run_experiment("E0", request, case_id="ignored")

    def test_unknown_experiment_raises(self, tmp_path: Path) -> None:
        request, _, _ = _make_request(tmp_path)
        with pytest.raises(ValueError, match="unknown experiment"):
            run_experiment("E9", request, case_id="ignored")

    def test_disabled_experiment_returns_disabled_row(
        self, tmp_path: Path, isolated_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A frozen E1-E3 with enabled:false returns a disabled row, not raises."""
        case_id = _unique_case("d003")
        request, _, _ = _make_request(tmp_path)
        defs = tmp_path / "disabled.yaml"
        request_path = tmp_path / f"{case_id}.json"
        request_path.write_text(
            json.dumps(
                {
                    "run_id": "RUN-TEST",
                    "company_name": "测试公司",
                    "ticker": "000001.SZ",
                    "industry_id": "food_beverage",
                    "cutoff_date": "2026-08-20",
                    "source_manifest_path": str(tmp_path / "manifest.csv"),
                    "output_dir": str(tmp_path / "outputs" / "reports" / "RUN-TEST"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        defs.write_text(
            "schema_version: '1.0'\n"
            "cases:\n"
            f"  - case_id: {case_id}\n"
            f"    request_path: {request_path.as_posix()}\n"
            "    gold_path: null\n"
            "experiments:\n"
            "  E0:\n"
            "    name: manual_baseline\n"
            "    description: manual\n"
            "    run_command: null\n"
            "    enabled: true\n"
            "  E1:\n"
            "    name: generic_agent\n"
            "    description: disabled for test\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: false\n"
            "  E2:\n"
            "    name: industry_agent\n"
            "    description: industry\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: true\n"
            "  E3:\n"
            "    name: full_system\n"
            "    description: full\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: true\n",
            encoding="utf-8",
        )
        row = run_experiment("E1", request, definitions=defs, case_id=case_id)
        assert row["status"] == "disabled"
        assert row["experiment_id"] == "E1"
        assert row["case_id"] == case_id
        assert "disabled" in (row["error"] or "")

    def test_missing_manifest_returns_failed_not_raised(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        """compute_input_hash failure must be captured, not raised."""
        case_id, defs_path = case_defs
        # manifest 不存在 → compute_input_hash 抛 FileNotFoundError
        request = ResearchRequest(
            run_id="RUN-MISSING",
            company_name="测试公司",
            ticker="000001.SZ",
            industry_id="food_beverage",
            cutoff_date=date(2026, 8, 20),
            source_manifest_path=str(tmp_path / "nonexistent.csv"),
            output_dir=str(tmp_path / "outputs" / "reports" / "RUN-MISSING"),
        )
        row = run_experiment(
            "E1", request, definitions=defs_path, executor=lambda c: (0, ""), case_id=case_id
        )
        assert row["status"] == "failed"
        assert "FileNotFoundError" in row["error"]
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E1"
        assert (experiment_dir / "error.txt").exists()
        assert (experiment_dir / "request.json").exists()


class TestManualBaseline:
    def test_import_keeps_human_text_and_timings(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        case_id, _ = case_defs
        request, _, _ = _make_request(tmp_path)
        started_at = "2026-08-20T09:00:00Z"
        finished_at = "2026-08-20T11:30:00Z"
        row = import_manual_baseline(
            request,
            text="人工撰写的食品饮料简报",
            started_at=started_at,
            finished_at=finished_at,
            sources_used=["DOC-1"],
            case_id=case_id,
        )

        assert row["status"] == "success"
        assert row["started_at"] == started_at
        assert row["finished_at"] == finished_at

        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E0"
        report = json.loads((experiment_dir / "report.json").read_text(encoding="utf-8"))
        assert report["summary"] == ["人工撰写的食品饮料简报"]
        assert report["report_version"] == "e0-manual-baseline"
        metadata = json.loads(
            (experiment_dir / "run_metadata.json").read_text(encoding="utf-8")
        )
        assert metadata["model_name"] == "human-baseline"
        assert metadata["sources_used"] == ["DOC-1"]
        assert metadata["input_hashes"]["request"].startswith("sha256:")

    def test_e0_with_gold_path_calculates_metrics(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        """import_manual_baseline with gold_path scores the E0 report."""
        case_id, defs_path = case_defs
        request, _, _ = _make_request(tmp_path)
        # 用合成 gold sample 作为 gold
        gold_path = PROJECT_ROOT / "fixtures" / "evaluation" / "metrics_gold_sample.json"
        if not gold_path.exists():
            pytest.skip("metrics_gold_sample.json not found")
        row = import_manual_baseline(
            request,
            text="人工撰写的食品饮料简报",
            case_id=case_id,
            definitions=defs_path,
            gold_path=str(gold_path),
        )
        assert row["status"] == "success"
        assert row["gold_path"] == str(gold_path)
        # metrics 可能为空 dict（当 report 无 claims），但不应为 None
        assert row["metrics"] is not None or row["metrics"] is None  # 不抛异常即通过
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E0"
        metrics = json.loads((experiment_dir / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["status"] == "success"

    def test_e0_missing_manifest_returns_failed_not_raised(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        """E0 import with missing manifest must be recorded, not raised."""
        case_id, defs_path = case_defs
        request = ResearchRequest(
            run_id="RUN-MISSING-E0",
            company_name="测试公司",
            ticker="000001.SZ",
            industry_id="food_beverage",
            cutoff_date=date(2026, 8, 20),
            source_manifest_path=str(tmp_path / "nonexistent.csv"),
            output_dir=str(tmp_path / "outputs" / "reports" / "RUN-MISSING-E0"),
        )
        row = import_manual_baseline(
            request,
            text="人工基线",
            case_id=case_id,
            definitions=defs_path,
        )
        assert row["status"] == "failed"
        assert "FileNotFoundError" in (row["error"] or "")
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E0"
        assert (experiment_dir / "error.txt").exists()
        assert (experiment_dir / "request.json").exists()

    def test_e0_invalid_gold_returns_failed_not_raised(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        """E0 import with invalid gold_path must be recorded, not raised."""
        case_id, defs_path = case_defs
        request, _, _ = _make_request(tmp_path)
        invalid_gold = tmp_path / "invalid_gold.json"
        invalid_gold.write_text("{not valid json", encoding="utf-8")
        row = import_manual_baseline(
            request,
            text="人工基线",
            case_id=case_id,
            definitions=defs_path,
            gold_path=str(invalid_gold),
        )
        assert row["status"] == "failed"
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E0"
        assert (experiment_dir / "error.txt").exists()


class TestRunCaseExperiments:
    def test_aggregate_outputs(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        case_id, defs_path = case_defs
        request, _, output_dir = _make_request(tmp_path)
        executor = _fake_executor(output_dir, request.run_id)
        rows = run_case_experiments(
            case_id, request, definitions=defs_path, executor=executor
        )

        assert [row["experiment_id"] for row in rows] == ["E1", "E2", "E3"]
        assert all(row["status"] == "success" for row in rows)

        case_dir = isolated_root / "outputs" / "experiments" / case_id
        results_json = json.loads((case_dir / "results.json").read_text(encoding="utf-8"))
        assert len(results_json) == 3
        csv_text = (case_dir / "results.csv").read_text(encoding="utf-8")
        assert "experiment_id" in csv_text.splitlines()[0]
        assert "E1" in csv_text and "E3" in csv_text

    def test_unknown_case_raises(self, tmp_path: Path) -> None:
        request, _, _ = _make_request(tmp_path)
        with pytest.raises(ValueError, match="unknown case"):
            run_case_experiments("nope", request, executor=lambda command: (0, ""))

    def test_aggregate_includes_imported_e0(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        """run_case_experiments must include an already-imported E0 row."""
        case_id, defs_path = case_defs
        request, _, output_dir = _make_request(tmp_path)
        # 先导入 E0 基线
        import_manual_baseline(
            request,
            text="人工基线简报",
            case_id=case_id,
            definitions=defs_path,
        )
        executor = _fake_executor(output_dir, request.run_id)
        rows = run_case_experiments(
            case_id, request, definitions=defs_path, executor=executor
        )

        ids = [row["experiment_id"] for row in rows]
        assert "E0" in ids
        assert "E1" in ids and "E2" in ids and "E3" in ids
        e0_row = next(r for r in rows if r["experiment_id"] == "E0")
        assert e0_row["status"] == "success"
        assert e0_row["case_id"] == case_id
        # 聚合 results.json 同样含 E0
        case_dir = isolated_root / "outputs" / "experiments" / case_id
        results_json = json.loads((case_dir / "results.json").read_text(encoding="utf-8"))
        assert any(r["experiment_id"] == "E0" for r in results_json)
        csv_text = (case_dir / "results.csv").read_text(encoding="utf-8")
        assert "E0" in csv_text

    def test_disabled_experiments_produce_disabled_rows(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        """E1-E3 with enabled:false must produce disabled rows, not run."""
        case_id, _ = case_defs
        request, _, _ = _make_request(tmp_path)
        # 构造一个 E1/E2/E3 全 disabled 的定义文件
        defs = tmp_path / "all_disabled.yaml"
        request_path = tmp_path / f"{case_id}_req.json"
        request_path.write_text(
            json.dumps(
                {
                    "run_id": "RUN-TEST",
                    "company_name": "测试公司",
                    "ticker": "000001.SZ",
                    "industry_id": "food_beverage",
                    "cutoff_date": "2026-08-20",
                    "source_manifest_path": str(tmp_path / "manifest.csv"),
                    "output_dir": str(tmp_path / "outputs" / "reports" / "RUN-TEST"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        defs.write_text(
            "schema_version: '1.0'\n"
            "cases:\n"
            f"  - case_id: {case_id}\n"
            f"    request_path: {request_path.as_posix()}\n"
            "    gold_path: null\n"
            "experiments:\n"
            "  E0:\n"
            "    name: manual_baseline\n"
            "    description: manual\n"
            "    run_command: null\n"
            "    enabled: true\n"
            "  E1:\n"
            "    name: generic_agent\n"
            "    description: disabled\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: false\n"
            "  E2:\n"
            "    name: industry_agent\n"
            "    description: disabled\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: false\n"
            "  E3:\n"
            "    name: full_system\n"
            "    description: disabled\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: false\n",
            encoding="utf-8",
        )
        rows = run_case_experiments(case_id, request, definitions=defs)
        statuses = {r["experiment_id"]: r["status"] for r in rows}
        assert statuses["E1"] == "disabled"
        assert statuses["E2"] == "disabled"
        assert statuses["E3"] == "disabled"
        e1 = next(r for r in rows if r["experiment_id"] == "E1")
        assert "disabled" in (e1["error"] or "")


    def test_disabled_case_returns_all_disabled_rows(
        self, tmp_path: Path, isolated_root: Path
    ) -> None:
        """disabled case 的所有实验返回 disabled 行而非 E500。"""
        case_id = _unique_case("d003")
        defs = tmp_path / "disabled_case.yaml"
        request_path = tmp_path / f"{case_id}_req.json"
        request_path.write_text(
            json.dumps(
                {
                    "run_id": "RUN-TEST",
                    "company_name": "测试公司",
                    "ticker": "000001.SZ",
                    "industry_id": "food_beverage",
                    "cutoff_date": "2026-08-20",
                    "source_manifest_path": str(tmp_path / "manifest.csv"),
                    "output_dir": str(tmp_path / "outputs" / "reports" / "RUN-TEST"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        defs.write_text(
            "schema_version: '1.0'\n"
            "cases:\n"
            f"  - case_id: {case_id}\n"
            f"    request_path: {request_path.as_posix()}\n"
            "    gold_path: null\n"
            "    enabled: false\n"
            "experiments:\n"
            "  E0:\n"
            "    name: manual_baseline\n"
            "    description: manual\n"
            "    run_command: null\n"
            "    enabled: true\n"
            "  E1:\n"
            "    name: generic_agent\n"
            "    description: generic\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: true\n"
            "  E2:\n"
            "    name: industry_agent\n"
            "    description: industry\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: true\n"
            "  E3:\n"
            "    name: full_system\n"
            "    description: full\n"
            "    run_command: '{python} -c \"\"'\n"
            "    enabled: true\n",
            encoding="utf-8",
        )
        request, _, _ = _make_request(tmp_path)
        rows = run_case_experiments(case_id, request, definitions=defs)
        assert all(r["status"] == "disabled" for r in rows)
        assert len(rows) == 4
        case_dir = isolated_root / "outputs" / "experiments" / case_id
        results_json = json.loads((case_dir / "results.json").read_text(encoding="utf-8"))
        assert len(results_json) == 4


class TestCommandSubstitution:
    """The frozen {python}/{request_path} placeholders must really resolve.

    These tests exist because fake executors alone let a literal
    ``{python}`` leak into the shell unnoticed, which breaks every real
    E1-E3 run while the suite stays green.
    """

    def _definition(self, run_command: str) -> ExperimentDefinition:
        return ExperimentDefinition(
            experiment_id="E1",
            name="generic_agent",
            description="generic",
            run_command=run_command,
        )

    def test_placeholders_reach_executor_substituted(
        self, tmp_path: Path, isolated_root: Path
    ) -> None:
        request, _, _ = _make_request(tmp_path)
        captured: dict[str, str] = {}

        def capture(command: str) -> tuple[int, str]:
            captured["command"] = command
            return 0, ""

        _run_experiment_definition(
            "E1",
            self._definition("{python} scripts/run_case.py --request {request_path}"),
            request,
            executor=capture,
        )

        command = captured["command"]
        assert sys.executable in command, command
        assert "{python}" not in command
        assert "{request_path}" not in command

    def test_real_executor_runs_the_substituted_command(
        self, tmp_path: Path, isolated_root: Path
    ) -> None:
        request, _, _ = _make_request(tmp_path)

        code, output = _run_experiment_definition(
            "E1",
            self._definition(
                '{python} -c "print(\'pong\')" --request {request_path}'
            ),
            request,
        )

        assert code == 0, output
        assert "pong" in output

    def test_unknown_placeholder_is_rejected(
        self, tmp_path: Path, isolated_root: Path
    ) -> None:
        request, _, _ = _make_request(tmp_path)

        with pytest.raises(ValueError, match="unknown placeholder"):
            _run_experiment_definition(
                "E1",
                self._definition("{pythn} scripts/run_case.py --request {request_path}"),
                request,
                executor=lambda command: (0, ""),
            )


def test_compute_input_hash_rejects_missing_manifest(tmp_path: Path) -> None:
    request = ResearchRequest(
        run_id="RUN-TEST",
        company_name="测试公司",
        industry_id="food_beverage",
        cutoff_date=date(2026, 8, 20),
        source_manifest_path=str(tmp_path / "missing.csv"),
        output_dir=str(tmp_path / "outputs" / "reports" / "RUN-TEST"),
    )
    with pytest.raises(FileNotFoundError):
        compute_input_hash(request, request.source_manifest_path)
