"""Context pack generation with token budgeting."""

from __future__ import annotations

import sqlite3
from typing import Optional

from openbook.core.models import ContextPack, MemoryCard
from openbook.core.search import search_memories

BUDGET_LIMITS = {
    "tiny": 700,
    "normal": 2000,
    "deep": 6000,
}

# Rough token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def build_context_pack(
    conn: sqlite3.Connection,
    project_id: int,
    query: str,
    budget: str = "normal",
    chapter: Optional[str] = None,
    memory_type: Optional[str] = None,
    tags: Optional[list[str]] = None,
    include_raw: bool = False,
    agent_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> ContextPack:
    token_budget = BUDGET_LIMITS.get(budget, BUDGET_LIMITS["normal"])
    cards = search_memories(
        conn=conn,
        project_id=project_id,
        query=query,
        chapter=chapter,
        memory_type=memory_type,
        tags=tags,
        status="approved",
        limit=50,
    )

    selected: list[MemoryCard] = []
    total_tokens = estimate_tokens(f"Context Pack: {query}\n")

    for card in cards:
        card_text = card.to_text(include_raw=include_raw)
        card_tokens = estimate_tokens(card_text)
        if total_tokens + card_tokens > token_budget:
            break
        selected.append(card)
        total_tokens += card_tokens

    # Log retrieval
    conn.execute(
        """
        INSERT INTO retrieval_logs (project_id, agent_id, session_id, query, budget, results_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            agent_id,
            session_id,
            query,
            budget,
            str([c.memory_id for c in selected]),
        ),
    )

    return ContextPack(
        query=query,
        budget=budget,
        cards=selected,
        total_tokens=total_tokens,
    )
