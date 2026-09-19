import os
import sqlite3
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cognify.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_sessions_db():
    """Initializes study_sessions and session_messages tables and indexes."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NULL,
                guest_id TEXT NULL,
                title TEXT NOT NULL DEFAULT 'New Study Session',
                pdf_filename TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                engine TEXT NULL,
                latency_ms INTEGER NULL,
                sources_json TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES study_sessions(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON study_sessions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_guest ON study_sessions(guest_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON study_sessions(updated_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id);")
        conn.commit()

init_sessions_db()

def clean_title_from_prompt(prompt: str) -> str:
    """Derives a concise, professional study session title from a user's initial prompt."""
    if not prompt:
        return "Study Session"
    cleaned = prompt.strip()
    cleaned = re.sub(r'^(explain|what is|what are|describe|how does|how do|tell me about|summarize|give me|can you explain)\s+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[?!.,;]+$', '', cleaned).strip()
    words = cleaned.split()
    if len(words) > 7:
        cleaned = " ".join(words[:7]) + "..."
    elif len(words) == 0:
        cleaned = "Study Session"
    else:
        cleaned = " ".join(words)
    # Capitalize first letter while preserving uppercase acronyms (CPU, OS, AI, etc.)
    if len(cleaned) > 0:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned[:60]

def create_session(
    session_id: str,
    user_id: Optional[int] = None,
    guest_id: Optional[str] = None,
    title: Optional[str] = None,
    pdf_filename: Optional[str] = None
) -> Dict[str, Any]:
    """Creates a new study session record in SQLite."""
    session_title = title.strip() if title and title.strip() else "New Study Session"
    now_iso = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_sessions (id, user_id, guest_id, title, pdf_filename, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                user_id = coalesce(excluded.user_id, study_sessions.user_id),
                guest_id = coalesce(excluded.guest_id, study_sessions.guest_id),
                pdf_filename = coalesce(excluded.pdf_filename, study_sessions.pdf_filename),
                updated_at = excluded.updated_at
            """,
            (session_id, user_id, guest_id, session_title, pdf_filename, now_iso, now_iso)
        )
        conn.commit()

    return {
        "id": session_id,
        "user_id": user_id,
        "guest_id": guest_id,
        "title": session_title,
        "pdf_filename": pdf_filename,
        "created_at": now_iso,
        "updated_at": now_iso
    }

def add_session_message(
    session_id: str,
    role: str,
    content: str,
    engine: Optional[str] = None,
    latency_ms: Optional[int] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[int] = None,
    guest_id: Optional[str] = None,
    pdf_filename: Optional[str] = None
) -> Dict[str, Any]:
    """Appends a user, assistant, or system message to the session."""
    now_iso = datetime.utcnow().isoformat()
    sources_json = json.dumps(sources) if sources else None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, pdf_filename FROM study_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            derived_title = clean_title_from_prompt(content) if role == "user" else "New Study Session"
            cursor.execute(
                """
                INSERT INTO study_sessions (id, user_id, guest_id, title, pdf_filename, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, guest_id, derived_title, pdf_filename, now_iso, now_iso)
            )
        else:
            updates = ["updated_at = ?"]
            params = [now_iso]
            if row["title"] == "New Study Session" and role == "user":
                updates.append("title = ?")
                params.append(clean_title_from_prompt(content))
            if pdf_filename and not row["pdf_filename"]:
                updates.append("pdf_filename = ?")
                params.append(pdf_filename)
            params.append(session_id)
            cursor.execute(f"UPDATE study_sessions SET {', '.join(updates)} WHERE id = ?", params)

        cursor.execute(
            """
            INSERT INTO session_messages (session_id, role, content, engine, latency_ms, sources_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, engine, latency_ms, sources_json, now_iso)
        )
        msg_id = cursor.lastrowid
        conn.commit()

    return {
        "id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "engine": engine,
        "latency_ms": latency_ms,
        "sources": sources or [],
        "created_at": now_iso
    }

def get_user_sessions(user_id: Optional[int] = None, guest_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all sessions for a user or guest, sorted newest first with message metrics."""
    if not user_id and not guest_id:
        return []

    query = """
        SELECT 
            s.id,
            s.user_id,
            s.guest_id,
            s.title,
            s.pdf_filename,
            s.created_at,
            s.updated_at,
            COUNT(m.id) as message_count,
            MAX(m.engine) as last_engine,
            (SELECT content FROM session_messages WHERE session_id = s.id AND role = 'user' ORDER BY id ASC LIMIT 1) as first_query,
            (SELECT content FROM session_messages WHERE session_id = s.id AND role = 'assistant' ORDER BY id DESC LIMIT 1) as last_reply
        FROM study_sessions s
        LEFT JOIN session_messages m ON s.id = m.session_id
        WHERE 
    """
    params = []
    if user_id:
        query += "s.user_id = ? "
        params.append(user_id)
    else:
        query += "s.guest_id = ? "
        params.append(guest_id)

    query += "GROUP BY s.id ORDER BY s.updated_at DESC"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "guest_id": r["guest_id"],
            "title": r["title"],
            "pdf_filename": r["pdf_filename"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "message_count": r["message_count"] or 0,
            "last_engine": r["last_engine"] or "",
            "preview": (r["first_query"] or r["last_reply"] or "")[:120]
        })
    return results

def get_session_details(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full session info and all chronological messages."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, guest_id, title, pdf_filename, created_at, updated_at
            FROM study_sessions
            WHERE id = ?
        """, (session_id,))
        session_row = cursor.fetchone()

        if not session_row:
            return None

        cursor.execute("""
            SELECT id, role, content, engine, latency_ms, sources_json, created_at
            FROM session_messages
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,))
        message_rows = cursor.fetchall()

    messages = []
    for m in message_rows:
        sources = []
        if m["sources_json"]:
            try:
                sources = json.loads(m["sources_json"])
            except Exception:
                sources = []
        messages.append({
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "engine": m["engine"] or "",
            "latency_ms": m["latency_ms"],
            "sources": sources,
            "created_at": m["created_at"]
        })

    return {
        "id": session_row["id"],
        "user_id": session_row["user_id"],
        "guest_id": session_row["guest_id"],
        "title": session_row["title"],
        "pdf_filename": session_row["pdf_filename"],
        "created_at": session_row["created_at"],
        "updated_at": session_row["updated_at"],
        "messages": messages,
        "message_count": len(messages)
    }

def update_session_title(session_id: str, title: str) -> bool:
    """Updates the title of a study session."""
    clean_title = title.strip()
    if not clean_title:
        return False

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE study_sessions 
            SET title = ?, updated_at = ?
            WHERE id = ?
        """, (clean_title[:80], datetime.utcnow().isoformat(), session_id))
        conn.commit()
        return cursor.rowcount > 0

def update_session_doc(session_id: str, pdf_filename: Optional[str]) -> bool:
    """Updates the attached PDF document for a session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE study_sessions 
            SET pdf_filename = ?, updated_at = ?
            WHERE id = ?
        """, (pdf_filename, datetime.utcnow().isoformat(), session_id))
        conn.commit()
        return cursor.rowcount > 0

def delete_session(session_id: str) -> bool:
    """Deletes a study session and cascade deletes its messages."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM study_sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0

def migrate_guest_sessions(guest_id: str, user_id: int) -> int:
    """Transfers all guest sessions to an authenticated user upon sign-in/registration."""
    if not guest_id or not user_id:
        return 0

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE study_sessions 
            SET user_id = ?, guest_id = NULL, updated_at = ?
            WHERE guest_id = ?
        """, (user_id, datetime.utcnow().isoformat(), guest_id))
        conn.commit()
        return cursor.rowcount

def get_study_analytics(user_id: Optional[int] = None, guest_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Collects aggregate statistics and data across all previous sessions.
    """
    if not user_id and not guest_id:
        return {
            "total_sessions": 0,
            "total_messages": 0,
            "user_questions": 0,
            "ai_answers": 0,
            "total_words": 0,
            "documents_count": 0,
            "documents_list": [],
            "engine_breakdown": {},
            "avg_latency_ms": 0
        }

    where_clause = "s.user_id = ?" if user_id else "s.guest_id = ?"
    param = user_id if user_id else guest_id

    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT s.id) as total_sessions,
                COUNT(DISTINCT s.pdf_filename) as documents_count
            FROM study_sessions s
            WHERE {where_clause}
        """, (param,))
        s_row = cursor.fetchone()
        total_sessions = s_row["total_sessions"] if s_row else 0

        cursor.execute(f"""
            SELECT DISTINCT s.pdf_filename
            FROM study_sessions s
            WHERE {where_clause} AND s.pdf_filename IS NOT NULL AND s.pdf_filename != ''
        """, (param,))
        doc_rows = cursor.fetchall()
        doc_list = [r["pdf_filename"] for r in doc_rows if r["pdf_filename"]]

        cursor.execute(f"""
            SELECT 
                m.role,
                m.content,
                m.engine,
                m.latency_ms
            FROM session_messages m
            JOIN study_sessions s ON m.session_id = s.id
            WHERE {where_clause}
        """, (param,))
        msg_rows = cursor.fetchall()

    user_questions = 0
    ai_answers = 0
    total_words = 0
    engine_counts: Dict[str, int] = {}
    latencies = []

    for m in msg_rows:
        content = m["content"] or ""
        total_words += len(content.split())
        role = m["role"]
        if role == "user":
            user_questions += 1
        elif role == "assistant":
            ai_answers += 1
            engine = m["engine"] or "Cognify Copilot"
            clean_engine = engine.replace("✨ ", "").replace("⚡ ", "").replace("🏎️ ", "").split(" (")[0].strip()
            engine_counts[clean_engine] = engine_counts.get(clean_engine, 0) + 1
            if m["latency_ms"] and m["latency_ms"] > 0:
                latencies.append(m["latency_ms"])

    avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0

    return {
        "total_sessions": total_sessions,
        "total_messages": len(msg_rows),
        "user_questions": user_questions,
        "ai_answers": ai_answers,
        "total_words": total_words,
        "documents_count": len(doc_list),
        "documents_list": doc_list,
        "engine_breakdown": engine_counts,
        "avg_latency_ms": avg_latency
    }
