"""Compatibility wrapper for the packaged OpenBook repo memory benchmark."""

from __future__ import annotations

from openbook.benchmarks.repo_memory import main


if __name__ == "__main__":
    raise SystemExit(main())
