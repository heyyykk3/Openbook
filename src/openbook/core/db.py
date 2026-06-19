"""Database schema, migrations, and connection management for OpenBook."""

import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import Literal

SCHEMA_VERSION = 1

CREATE_SCHEMA_SQL = """
-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch())
);

-- Settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL DEFAULT (unixepoch())
);

-- Chapters
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch()),
    UNIQUE(project_id, name)
);

-- Sources
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    uri TEXT,
    title TEXT,
    metadata_json TEXT DEFAULT '{}',
    trust_score REAL DEFAULT 0.5,
    created_at REAL DEFAULT (unixepoch())
);

-- Citations
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    commit_hash TEXT,
    terminal_session_id TEXT,
    transcript_span_id TEXT,
    url TEXT,
    quote TEXT,
    metadata_json TEXT DEFAULT '{}',
    created_at REAL DEFAULT (unixepoch())
);

-- Memories
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    type TEXT NOT NULL,
    title TEXT,
    summary TEXT,
    content TEXT NOT NULL,
    tags_json TEXT DEFAULT '[]',
    confidence REAL DEFAULT 0.5,
    trust_score REAL DEFAULT 0.5,
    importance REAL DEFAULT 0.5,
    status TEXT DEFAULT 'proposed',
    valid_from REAL DEFAULT (unixepoch()),
    valid_to REAL,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    citation_id INTEGER REFERENCES citations(id) ON DELETE SET NULL,
    content_hash TEXT NOT NULL,
    idempotency_key TEXT,
    created_by_agent_id INTEGER,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch())
);

-- Chunks
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_hash TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    created_at REAL DEFAULT (unixepoch())
);

-- Embeddings
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector BLOB,
    content_hash TEXT NOT NULL,
    created_at REAL DEFAULT (unixepoch())
);

-- Relations
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    target_memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    created_at REAL DEFAULT (unixepoch())
);

-- Review queue
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    proposed_memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    proposed_by_agent_id INTEGER,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at REAL DEFAULT (unixepoch()),
    reviewed_at REAL
);

-- Retrieval logs
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_id INTEGER,
    session_id TEXT,
    query TEXT NOT NULL,
    budget TEXT,
    results_json TEXT DEFAULT '{}',
    created_at REAL DEFAULT (unixepoch())
);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    client_name TEXT,
    agent_name TEXT,
    version TEXT,
    hostname TEXT,
    created_at REAL DEFAULT (unixepoch()),
    last_seen_at REAL DEFAULT (unixepoch())
);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    client_name TEXT,
    process_id INTEGER,
    cwd TEXT,
    started_at REAL DEFAULT (unixepoch()),
    ended_at REAL,
    status TEXT DEFAULT 'active'
);

-- Events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at REAL DEFAULT (unixepoch())
);

-- Locks
CREATE TABLE IF NOT EXISTS locks (
    name TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL DEFAULT (unixepoch())
);

-- Handoffs
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    to_agent_hint TEXT,
    summary TEXT,
    context_pack_json TEXT DEFAULT '{}',
    created_at REAL DEFAULT (unixepoch())
);

-- FTS5 virtual table for memories
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    title,
    tags_json,
    content='memories',
    content_rowid='id'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, title, tags_json)
    VALUES (new.id, new.content, new.title, new.tags_json);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, title, tags_json)
    VALUES ('delete', old.id, old.content, old.title, old.tags_json);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, title, tags_json)
    VALUES ('delete', old.id, old.content, old.title, old.tags_json);
    INSERT INTO memories_fts(rowid, content, title, tags_json)
    VALUES (new.id, new.content, new.title, new.tags_json);
END;
"""

DEFAULT_CHAPTERS = [
    ("architecture", "System architecture and design decisions"),
    ("conventions", "Coding conventions and style guidelines"),
    ("commands", "Common commands and scripts"),
    ("decisions", "Project decisions and ADRs"),
    ("failures", "Failures, incidents, and lessons learned"),
    ("dependencies", "Dependencies and external libraries"),
    ("apis", "API documentation and contracts"),
    ("tests", "Testing practices and test suites"),
    ("deployment", "Deployment and infrastructure notes"),
    ("security", "Security considerations and policies"),
    ("roadmap", "Project roadmap and future plans"),
    ("handoffs", "Agent handoff notes and context"),
]

MIGRATIONS: dict[int, str] = {}


class OpenBookConnection(sqlite3.Connection):
    """SQLite connection whose context manager commits/rolls back and closes."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return False


def _get_db_path(project_root: Path) -> Path:
    return (project_root / ".openbook" / "openbook.sqlite").expanduser().resolve()


def _pragma_setup(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")


def _connect_sqlite(db_path: Path, timeout: float) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(
            str(db_path),
            timeout=timeout,
            isolation_level=None,
            factory=OpenBookConnection,
        )
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"unable to open SQLite database at {db_path}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        _pragma_setup(conn)
    except Exception:
        conn.close()
        raise
    return conn


def get_connection(project_root: Path, timeout: float = 5.0) -> sqlite3.Connection:
    return _connect_sqlite(_get_db_path(project_root), timeout)


def _acquire_migration_lock(conn: sqlite3.Connection, holder: str) -> bool:
    now = time.time()
    expires = now + 30.0
    try:
        conn.execute(
            "INSERT INTO locks (name, holder, expires_at) VALUES ('schema_migration', ?, ?)",
            (holder, expires),
        )
        return True
    except sqlite3.IntegrityError:
        # Check if expired
        row = conn.execute(
            "SELECT expires_at FROM locks WHERE name = 'schema_migration'"
        ).fetchone()
        if row and row["expires_at"] < now:
            conn.execute(
                "UPDATE locks SET holder = ?, expires_at = ? WHERE name = 'schema_migration'",
                (holder, expires),
            )
            return True
        return False


def _release_migration_lock(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM locks WHERE name = 'schema_migration'")


def initialize_database(project_root: Path) -> None:
    db_path = _get_db_path(project_root)
    conn = _connect_sqlite(db_path, timeout=30.0)

    # The migration lock has to exist before we can acquire it on a fresh DB.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS locks (
            name TEXT PRIMARY KEY,
            holder TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at REAL DEFAULT (unixepoch())
        )
    """)

    holder = f"pid-{os.getpid()}-thread-{threading.current_thread().ident}"
    if not _acquire_migration_lock(conn, holder):
        conn.close()
        raise RuntimeError("Another process is currently running schema migrations.")

    try:
        # Ensure projects table exists for parameterized chapter inserts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_path TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch())
            )
        """)

        # Insert or get project
        conn.execute(
            "INSERT OR IGNORE INTO projects (root_path, name) VALUES (?, ?)",
            (str(project_root.resolve()), project_root.name),
        )

        # Run DDL schema (tables, triggers, FTS)
        conn.executescript(CREATE_SCHEMA_SQL)

        # Insert default chapters via parameterized query
        root_str = str(project_root.resolve())
        project_row = conn.execute(
            "SELECT id FROM projects WHERE root_path = ?", (root_str,)
        ).fetchone()
        project_id = project_row["id"] if project_row else None
        if project_id:
            for name, description in DEFAULT_CHAPTERS:
                conn.execute(
                    "INSERT OR IGNORE INTO chapters (project_id, name, description) VALUES (?, ?, ?)",
                    (project_id, name, description),
                )

        # Schema version tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        existing = conn.execute("SELECT version FROM _schema_version").fetchone()
        current_version = existing[0] if existing else 0
        for v in range(current_version + 1, SCHEMA_VERSION + 1):
            if v in MIGRATIONS:
                conn.executescript(MIGRATIONS[v])
            conn.execute("INSERT OR REPLACE INTO _schema_version (version) VALUES (?)", (v,))
    finally:
        _release_migration_lock(conn)
        conn.close()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
