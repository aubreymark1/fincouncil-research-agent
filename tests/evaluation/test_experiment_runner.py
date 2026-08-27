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
        "  E1:\n"
        "    name: generic_agent\n"
        "    description: generic\n"
        "    run_command: '{python} scripts/run_case.py --request {request_path}'\n"
        "  E2:\n"
        "    name: industry_agent\n"
        "    description: industry\n"
        "    run_command: '{python} scripts/run_case.py --request {request_path}'\n"
        "  E3:\n"
        "    name: full_system\n"
        "    description: full\n"
        "    run_command: '{python} scripts/run_case.py --request {request_path}'\n",
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
        case_id, _ = case_defs
        request, _, output_dir = _make_request(tmp_path)
        executor = _fake_executor(output_dir, request.run_id)
        row = run_experiment(
            "E1", request, executor=executor, case_id=case_id
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
        case_id, _ = case_defs
        request, _, output_dir = _make_request(tmp_path)
        executor = _fake_executor(output_dir, request.run_id, code=1, output="boom")
        row = run_experiment(
            "E2", request, executor=executor, case_id=case_id
        )

        assert row["status"] == "failed"
        assert "boom" in row["error"]
        experiment_dir = isolated_root / "outputs" / "experiments" / case_id / "E2"
        assert (experiment_dir / "error.txt").exists()
        assert (experiment_dir / "report.json").exists()
        assert (experiment_dir / "request.json").exists()

    def test_crashed_pipeline_keeps_error_file(
        self, tmp_path: Path, isolated_root: Path, case_defs
    ) -> None:
        case_id, _ = case_defs
        request, _, output_dir = _make_request(tmp_path)

        def crashed_executor(command: str) -> tuple[int, str]:
            return 0, ""

        row = run_experiment(
            "E3", request, executor=crashed_executor, case_id=case_id
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
