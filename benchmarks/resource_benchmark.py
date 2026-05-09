"""Compatibility wrapper for the packaged OpenBook resource benchmark."""

from __future__ import annotations

from openbook.benchmarks.resource import main


if __name__ == "__main__":
    raise SystemExit(main())
