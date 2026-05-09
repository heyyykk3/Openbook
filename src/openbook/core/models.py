"""Data models and helpers for OpenBook."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Project:
    id: int
    root_path: str
    name: str
    created_at: float
    updated_at: float


@dataclass
class Chapter:
    id: int
    project_id: int
    name: str
    description: Optional[str]
    created_at: float
    updated_at: float


@dataclass
class Source:
    id: int
    project_id: int
    type: str
    uri: Optional[str]
    title: Optional[str]
    metadata: dict[str, Any]
    trust_score: float
    created_at: float


@dataclass
class Citation:
    id: int
    source_id: Optional[int]
    project_id: int
    file_path: Optional[str]
    line_start: Optional[int]
    line_end: Optional[int]
    commit_hash: Optional[str]
    terminal_session_id: Optional[str]
    transcript_span_id: Optional[str]
    url: Optional[str]
    quote: Optional[str]
    metadata: dict[str, Any]
    created_at: float

    def format(self) -> str:
        parts = []
        if self.file_path:
            loc = self.file_path
            if self.line_start is not None:
                loc += f" lines {self.line_start}"
                if self.line_end is not None and self.line_end != self.line_start:
                    loc += f"-{self.line_end}"
            parts.append(loc)
        if self.commit_hash:
            parts.append(f"commit {self.commit_hash}")
        if self.terminal_session_id:
            parts.append(f"terminal session {self.terminal_session_id}")
        if self.url:
            parts.append(self.url)
        if self.quote:
            parts.append(f'"{self.quote[:200]}"')
        if not parts:
            return "citation unavailable"
        return " | ".join(parts)


@dataclass
class Memory:
    id: int
    project_id: int
    chapter_id: Optional[int]
    type: str
    title: Optional[str]
    summary: Optional[str]
    content: str
    tags: list[str]
    confidence: float
    trust_score: float
    importance: float
    status: str
    valid_from: float
    valid_to: Optional[float]
    source_id: Optional[int]
    citation_id: Optional[int]
    content_hash: str
    idempotency_key: Optional[str]
    created_by_agent_id: Optional[int]
    created_at: float
    updated_at: float


@dataclass
class MemoryCard:
    rank: int
    memory_id: int
    title: Optional[str]
    summary: str
    tags: list[str]
    trust: str
    citation: Optional[str]
    raw_excerpt: Optional[str] = None

    def to_text(self, include_raw: bool = False) -> str:
        lines = [
            f"{self.rank}. {self.summary}",
        ]
        if self.citation:
            lines.append(f"   Citation: {self.citation}")
        lines.append(f"   Trust: {self.trust}")
        if include_raw and self.raw_excerpt:
            lines.append(f"   Excerpt: {self.raw_excerpt[:400]}")
        return "\n".join(lines)


@dataclass
class ContextPack:
    query: str
    budget: str
    cards: list[MemoryCard]
    total_tokens: int = 0

    def to_text(self, include_raw: bool = False) -> str:
        lines = [f"Context Pack: {self.query}", ""]
        for card in self.cards:
            lines.append(card.to_text(include_raw=include_raw))
            lines.append("")
        lines.append(f"Budget: {self.budget} | Cards: {len(self.cards)} | Estimated tokens: {self.total_tokens}")
        return "\n".join(lines)


def parse_tags(tags_json: Optional[str]) -> list[str]:
    if not tags_json:
        return []
    try:
        data = json.loads(tags_json)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def format_tags(tags: list[str]) -> str:
    return json.dumps(tags)


def parse_metadata(metadata_json: Optional[str]) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        data = json.loads(metadata_json)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}
