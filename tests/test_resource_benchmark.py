from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "resource_benchmark.py"


def test_resource_benchmark_cli_writes_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    work_dir = tmp_path / "work"

    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--memories",
            "8",
            "--searches",
            "3",
            "--context-limit",
            "4",
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
    assert (report_dir / "summary.md").is_file()
    assert (report_dir / "results.json").is_file()


def test_resource_benchmark_json_shape(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    work_dir = tmp_path / "work"

    subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--memories",
            "6",
            "--searches",
            "2",
            "--report-dir",
            str(report_dir),
            "--work-dir",
            str(work_dir),
        ],
        check=True,
    )

    results = json.loads((report_dir / "results.json").read_text(encoding="utf-8"))
    assert results["benchmark"] == "openbook-resource"
    assert results["config"]["memories"] == 6
    assert results["database"]["size_bytes"] > 0
    assert results["database"]["bytes_per_memory"] > 0
    assert set(results["latency_ms"]) == {"insert", "search"}
    assert results["latency_ms"]["insert"]["p95"] >= 0
    assert results["latency_ms"]["search"]["p95"] >= 0
    assert results["context_pack"]["bytes"] > 0
    assert "peak_rss_bytes" in results["process_memory"]
