"""
AI 对话会话管理器

特性:
- SQLite 持久化存储（复用 geocache.db）
- 会话 CRUD + 消息追加
- 上下文构建（替代前端截断方案）
- /compact: AI 生成摘要替换历史
- 消息上限 200 条/session
"""

import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

from .config import OutputPaths

logger = logging.getLogger(__name__)

CURRENT_CHAT_SCHEMA_VERSION = 1

CREATE_CHAT_SESSIONS = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated_at);
"""

CREATE_CHAT_MESSAGES = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning TEXT DEFAULT '',
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, timestamp);
"""


class ChatManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(OutputPaths.DATABASE / "geocache.db")
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._path), timeout=30)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def connection(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def _ensure_schema(self) -> None:
        with self.connection() as conn:
            try:
                row = conn.execute(
                    "SELECT MAX(version) FROM _schema_version"
                ).fetchone()
                row[0] if row and row[0] is not None else 0
            except sqlite3.OperationalError:
                pass

            conn.executescript(CREATE_CHAT_SESSIONS)
            conn.executescript(CREATE_CHAT_MESSAGES)

            chat_version = 0
            try:
                row = conn.execute(
                    "SELECT version FROM _schema_version WHERE description = 'chat_v1'"
                ).fetchone()
                if row:
                    chat_version = row[0]
            except sqlite3.OperationalError:
                pass

            if chat_version < CURRENT_CHAT_SCHEMA_VERSION:
                conn.execute(
                    "INSERT OR REPLACE INTO _schema_version (version, applied_at, description) VALUES (?,?,?)",
                    (CURRENT_CHAT_SCHEMA_VERSION, time.time(), "chat_v1"),
                )

    # ── 会话 CRUD ─────────────────────────────────────────────

    def create_session(self, title: str = "") -> Dict:
        session_id = str(uuid.uuid4())
        now = time.time()
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                (session_id, title, now, now),
            )
        return {"id": session_id, "title": title, "created_at": now, "updated_at": now}

    def list_sessions(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> Optional[Dict]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str) -> bool:
        with self.connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        return True

    # ── 消息管理 ─────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        reasoning: str = "",
    ) -> Dict:
        msg_id = f"msg-{uuid.uuid4().hex[:8]}-{int(time.time()*1000)}"
        now = time.time()
        with self.connection() as conn:
            # 确保会话存在（前端可能未同步创建）
            existing = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO chat_sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                    (session_id, "", now, now),
                )

            conn.execute(
                "INSERT INTO chat_messages (id, session_id, role, content, reasoning, timestamp) VALUES (?,?,?,?,?,?)",
                (msg_id, session_id, role, content, reasoning, now),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            if msg_count > 200:
                excess = msg_count - 200
                conn.execute(
                    "DELETE FROM chat_messages WHERE id IN (SELECT id FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?)",
                    (session_id, excess),
                )
        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "reasoning": reasoning,
            "timestamp": now,
        }

    def get_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id, session_id, role, content, reasoning, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_messages(self, session_id: str) -> List[Dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id, session_id, role, content, reasoning, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── 上下文构建 ─────────────────────────────────────────────

    def build_context(self, session_id: str, max_messages: int = 30, max_content_len: int = 800) -> List[Dict]:
        messages = self.get_messages(session_id, limit=max_messages)
        if len(messages) > max_messages:
            messages = messages[-max_messages:]

        context: List[Dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            if role not in ("user", "assistant"):
                continue
            if role == "assistant" and len(content) > max_content_len:
                content = content[:max_content_len] + "..."
            context.append({"role": role, "content": content})
        return context

    # ── Compact: AI 摘要压缩 ──────────────────────────────────

    def compact_session(self, session_id: str, summary: str) -> int:
        with self.connection() as conn:
            conn.execute(
                "DELETE FROM chat_messages WHERE session_id = ?",
                (session_id,),
            )
            now = time.time()
            conn.execute(
                "INSERT INTO chat_messages (id, session_id, role, content, reasoning, timestamp) VALUES (?,?,?,?,?,?)",
                (f"msg-compact-{int(now*1000)}", session_id, "system", summary, "", now),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
        return 1

    # ── 工具 ─────────────────────────────────────────────

    def session_count(self) -> int:
        with self.connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()
        return row[0] if row else 0

    def message_count(self, session_id: str) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
