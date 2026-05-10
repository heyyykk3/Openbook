from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from openbook.benchmarks.repo_memory import run_benchmark, write_reports


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "repo_memory_benchmark.py"


def test_repo_memory_benchmark_scores_core_tasks(tmp_path: Path) -> None:
    results = run_benchmark(work_dir=tmp_path / "work", top_k=3)

    assert results["benchmark"] == "openbook-repo-memory"
    assert results["overall"]["task_count"] >= 10
    assert results["overall"]["hit@3"] >= 0.85
    assert results["overall"]["stale_or_secret_excluded"] == 1.0
    assert results["records"]


def test_repo_memory_benchmark_writes_reports(tmp_path: Path) -> None:
    results = run_benchmark(work_dir=tmp_path / "work", top_k=3)
    report_dir = tmp_path / "reports"

    write_reports(results, report_dir)

    assert (report_dir / "summary.md").is_file()
    assert (report_dir / "results.json").is_file()
    assert (report_dir / "records.jsonl").is_file()
    assert (report_dir / "metrics.csv").is_file()
    assert (report_dir / "charts" / "scorecard.svg").is_file()


def test_repo_memory_benchmark_wrapper_cli(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    work_dir = tmp_path / "work"

    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--report-dir",
            str(report_dir),
            "--work-dir",
            str(work_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "summary.md" in completed.stdout
    results = json.loads((report_dir / "results.json").read_text(encoding="utf-8"))
    assert results["benchmark"] == "openbook-repo-memory"
