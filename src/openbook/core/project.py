"""Project root detection and initialization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


KNOWN_ROOT_MARKERS = [
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Makefile",
]

README_NAMES = ["README.md", "README.rst", "README.txt", "README"]
AGENTS_MD_NAMES = ["AGENTS.md", "AGENTS.txt"]


def detect_project_root(cwd: Optional[Path] = None) -> Path:
    cwd = cwd or Path(os.getcwd())
    current = cwd.resolve()
    while True:
        for marker in KNOWN_ROOT_MARKERS:
            if (current / marker).exists():
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return cwd.resolve()


def detect_project_name(project_root: Path) -> str:
    for readme in README_NAMES:
        readme_path = project_root / readme
        if readme_path.exists():
            try:
                with open(readme_path, "r", encoding="utf-8") as f:
                    first = f.readline().strip()
                    if first.startswith("#"):
                        return first.lstrip("#").strip()
            except Exception:
                pass
    return project_root.name


def detect_stack(project_root: Path) -> list[str]:
    stacks = []
    if (project_root / "pyproject.toml").exists() or (project_root / "requirements.txt").exists():
        stacks.append("python")
    if (project_root / "package.json").exists():
        stacks.append("node")
    if (project_root / "Cargo.toml").exists():
        stacks.append("rust")
    if (project_root / "go.mod").exists():
        stacks.append("go")
    if (project_root / "composer.json").exists():
        stacks.append("php")
    return stacks
