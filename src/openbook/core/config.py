"""Configuration management for OpenBook."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import toml

DEFAULT_CONFIG = """
[storage]
database = ".openbook/openbook.sqlite"
vector_backend = "none"

[retrieval]
mode = "fts"
default_budget = "normal"

[embeddings]
provider = "none"
model = ""
base_url = ""
dimensions = 0
api_key_env = ""

[llm]
provider = "none"
model = ""
base_url = ""
api_key_env = ""
""".strip()


class Config:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def load(cls, project_root: Path) -> "Config":
        config_path = project_root / ".openbook" / "config.toml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = toml.load(f)
        else:
            data = {}
        # Merge with defaults
        default = toml.loads(DEFAULT_CONFIG)
        merged = _merge_dicts(default, data)
        return cls(merged)

    @classmethod
    def create_default(cls, project_root: Path) -> "Config":
        config_path = project_root / ".openbook" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if not config_path.exists():
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG + "\n")
        return cls.load(project_root)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    def section(self, name: str) -> dict[str, Any]:
        section = self._data.get(name, {})
        if not isinstance(section, dict):
            return {}
        return cast(dict[str, Any], section)

    def to_dict(self) -> dict[str, Any]:
        return self._data

    def save(self, project_root: Path) -> None:
        config_path = project_root / ".openbook" / "config.toml"
        with open(config_path, "w", encoding="utf-8") as f:
            toml.dump(self._data, f)


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
