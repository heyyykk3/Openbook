"""Security features for OpenBook."""

from __future__ import annotations

import re
from pathlib import Path

# Common secret patterns
SECRET_PATTERNS = [
    (r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?", "api_key"),
    (r"(?i)secret\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?", "secret"),
    (r"(?i)password\s*[:=]\s*['\"]?[^\s'\"]{8,}['\"]?", "password"),
    (r"(?i)token\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{20,}['\"]?", "token"),
    (r"(?i)private[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9+/=]{20,}['\"]?", "private_key"),
    (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
    (r"ghp_[a-zA-Z0-9]{36}", "github_token"),
    (r"sk-[a-zA-Z0-9]{48}", "openai_key"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "bearer_token"),
]

DEFAULT_OPENBOOKIGNORE = """
# OpenBook ignore patterns
.git
node_modules
vendor
dist
build
*.env
.env.*
secrets/
*.pem
*.key
*.p12
*.pfx
*.der
*.crt
*.lock
yarn.lock
package-lock.json
poetry.lock
Cargo.lock
composer.lock
go.sum
*.min.js
*.min.css
*.map
*.wasm
*.dll
*.so
*.dylib
*.exe
*.bin
*.zip
*.tar.gz
*.rar
*.7z
*.jpg
*.jpeg
*.png
*.gif
*.webp
*.mp4
*.mov
*.mp3
*.wav
*.pdf
*.doc
*.docx
""".strip()


def scan_for_secrets(text: str) -> list[str]:
    findings = []
    for pattern, name in SECRET_PATTERNS:
        if re.search(pattern, text):
            findings.append(name)
    return findings


def redact_secrets(text: str) -> str:
    for pattern, name in SECRET_PATTERNS:
        text = re.sub(pattern, f"[REDACTED:{name}]", text)
    return text


def ensure_openbookignore(project_root: Path) -> Path:
    ignore_path = project_root / ".openbookignore"
    if not ignore_path.exists():
        with open(ignore_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_OPENBOOKIGNORE + "\n")
    return ignore_path
