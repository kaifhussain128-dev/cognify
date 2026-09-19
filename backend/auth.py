import os
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cognify.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> tuple[str, str]:
    """Generates a random salt and derives a secure PBKDF2-SHA256 hash."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return pwd_hash, salt

def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Verifies a plain password against the stored salt and hash in constant time."""
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hmac.compare_digest(pwd_hash, expected_hash)

def generate_user_id() -> str:
    """Generates a unique branded student/user identifier, e.g. COG-849201."""
    while True:
        code = f"COG-{secrets.randbelow(900000) + 100000}"
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE public_id = ?", (code,))
            if not cursor.fetchone():
                return code

def init_db():
    """Initializes and migrates database tables, columns, indexes, and default administrator."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                path TEXT DEFAULT '/',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                auth_method TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # Alter users table for new columns if not present
        columns_to_add = [
            ("public_id", "TEXT", "NULL"),
            ("is_admin", "INTEGER", "0"),
            ("field_of_study", "TEXT", "'Computer Science & AI'"),
            ("study_goal", "TEXT", "'Master high-yield concepts & active recall'"),
            ("preferred_engine", "TEXT", "'auto'")
        ]
        for col, col_type, default_val in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type} DEFAULT {default_val}")
            except Exception:
                pass

        # Backfill public_id for any existing accounts
        cursor.execute("SELECT id FROM users WHERE public_id IS NULL OR public_id = ''")
        existing_users = cursor.fetchall()
        for u in existing_users:
            pid = f"COG-{100000 + u['id']}"
            cursor.execute("UPDATE users SET public_id = ? WHERE id = ?", (pid, u["id"]))

        # Seed Default Administrator Account
        cursor.execute("SELECT id FROM users WHERE email = 'admin@cognify.ai'")
        if not cursor.fetchone():
            admin_hash, admin_salt = hash_password("Admin@Cognify2026")
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, salt, public_id, is_admin, field_of_study, study_goal, preferred_engine)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                "Cognify Administrator",
                "admin@cognify.ai",
                admin_hash,
                admin_salt,
                "COG-ADMIN01",
                "Computer Science & Platform Administration",
                "Platform Security, Telemetry & User Insights Oversight",
                "auto"
            ))

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_visits_visitor ON site_visits(visitor_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_user ON login_logs(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_public_id ON users(public_id);")
        conn.commit()

# Initialize tables immediately upon module load
init_db()

def create_session(user_id: int, days_valid: int = 30) -> str:
    """Creates an active session token for a given user ID."""
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(days=days_valid)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at.isoformat())
        )
        conn.commit()
    return token

def log_user_login(user_id: int, email: str, auth_method: str = "password"):
    """Records a user login event into login_logs."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO login_logs (user_id, email, auth_method) VALUES (?, ?, ?)",
                (user_id, email.lower(), auth_method)
            )
            conn.commit()
    except Exception as e:
        print(f"[Warning] Failed to log user login: {e}")

def record_visit(visitor_id: str, path: str = "/") -> Dict[str, Any]:
    """Records a website visit for visitor analytics."""
    clean_vid = visitor_id.strip() if visitor_id else "anonymous"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO site_visits (visitor_id, path) VALUES (?, ?)",
            (clean_vid, path)
        )
        cursor.execute("SELECT COUNT(*) as total_visits, COUNT(DISTINCT visitor_id) as unique_visitors FROM site_visits")
        row = cursor.fetchone()
        conn.commit()
    return {
        "total_visits": row["total_visits"],
        "unique_visitors": row["unique_visitors"]
    }

def register_user(name: str, email: str, password: str) -> dict:
    """Registers a new user account, assigns a branded User ID, and returns the profile and session token."""
    clean_name = name.strip()
    clean_email = email.strip().lower()

    if not clean_name or len(clean_name) < 2:
        raise ValueError("Name must be at least 2 characters long.")
    if not clean_email or "@" not in clean_email:
        raise ValueError("Please provide a valid email address.")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    pwd_hash, salt = hash_password(password)
    public_id = generate_user_id()

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash, salt, public_id, is_admin)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (clean_name, clean_email, pwd_hash, salt, public_id)
            )
            user_id = cursor.lastrowid
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")

    token = create_session(user_id)
    log_user_login(user_id, clean_email, "email")

    return {
        "user": {
            "id": user_id,
            "public_id": public_id,
            "name": clean_name,
            "email": clean_email,
            "is_admin": 0,
            "field_of_study": "Computer Science & AI",
            "study_goal": "Master high-yield concepts & active recall",
            "preferred_engine": "auto"
        },
        "token": token
    }

def login_user(email: str, password: str) -> dict:
    """Authenticates a user with email and password."""
    clean_email = email.strip().lower()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, password_hash, salt, public_id, is_admin, field_of_study, study_goal, preferred_engine
            FROM users WHERE email = ?
        """, (clean_email,))
        row = cursor.fetchone()

    if not row:
        raise ValueError("Invalid email or password.")

    if not verify_password(password, row["salt"], row["password_hash"]):
        raise ValueError("Invalid email or password.")

    # Ensure public_id exists
    public_id = row["public_id"]
    if not public_id:
        public_id = f"COG-{100000 + row['id']}"
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET public_id = ? WHERE id = ?", (public_id, row["id"]))
            conn.commit()

    token = create_session(row["id"])
    log_user_login(row["id"], clean_email, "email")

    return {
        "user": {
            "id": row["id"],
            "public_id": public_id,
            "name": row["name"],
            "email": row["email"],
            "is_admin": row["is_admin"] or 0,
            "field_of_study": row["field_of_study"] or "Computer Science & AI",
            "study_goal": row["study_goal"] or "Master high-yield concepts & active recall",
            "preferred_engine": row["preferred_engine"] or "auto"
        },
        "token": token
    }

def get_user_by_token(token: str) -> dict | None:
    """Retrieves the user associated with an active, unexpired session token."""
    if not token:
        return None

    now_iso = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.public_id, u.is_admin, u.field_of_study, u.study_goal, u.preferred_engine, u.created_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, now_iso))
        row = cursor.fetchone()

    if not row:
        return None

    public_id = row["public_id"]
    if not public_id:
        public_id = f"COG-{100000 + row['id']}"

    return {
        "id": row["id"],
        "public_id": public_id,
        "name": row["name"],
        "email": row["email"],
        "is_admin": row["is_admin"] or 0,
        "field_of_study": row["field_of_study"] or "Computer Science & AI",
        "study_goal": row["study_goal"] or "Master high-yield concepts & active recall",
        "preferred_engine": row["preferred_engine"] or "auto",
        "created_at": row["created_at"]
    }

def logout_user(token: str) -> bool:
    """Revokes a session token."""
    if not token:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    return True

def google_auth_user(name: str, email: str) -> dict:
    """Authenticates or registers a user via their Google email in SQLite with User ID generation."""
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        raise ValueError("Please provide a valid Google email address.")

    clean_name = name.strip() if name else ""
    if not clean_name:
        clean_name = clean_email.split("@")[0].replace(".", " ").title()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, public_id, is_admin, field_of_study, study_goal, preferred_engine
            FROM users WHERE email = ?
        """, (clean_email,))
        row = cursor.fetchone()

        if row:
            public_id = row["public_id"]
            if not public_id:
                public_id = f"COG-{100000 + row['id']}"
                cursor.execute("UPDATE users SET public_id = ? WHERE id = ?", (public_id, row["id"]))
                conn.commit()

            token = create_session(row["id"])
            log_user_login(row["id"], clean_email, "google")
            return {
                "user": {
                    "id": row["id"],
                    "public_id": public_id,
                    "name": row["name"],
                    "email": row["email"],
                    "is_admin": row["is_admin"] or 0,
                    "field_of_study": row["field_of_study"] or "Computer Science & AI",
                    "study_goal": row["study_goal"] or "Master high-yield concepts & active recall",
                    "preferred_engine": row["preferred_engine"] or "auto"
                },
                "token": token
            }

        # User does not exist yet: create in SQLite database
        pwd_hash, salt = hash_password(secrets.token_hex(16))
        public_id = generate_user_id()
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, salt, public_id, is_admin)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (clean_name, clean_email, pwd_hash, salt, public_id))
        user_id = cursor.lastrowid
        conn.commit()

        token = create_session(user_id)
        log_user_login(user_id, clean_email, "google")

        return {
            "user": {
                "id": user_id,
                "public_id": public_id,
                "name": clean_name,
                "email": clean_email,
                "is_admin": 0,
                "field_of_study": "Computer Science & AI",
                "study_goal": "Master high-yield concepts & active recall",
                "preferred_engine": "auto"
            },
            "token": token
        }

def get_user_profile(user_id: int) -> Dict[str, Any]:
    """Retrieves detailed user profile data and learning statistics."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, public_id, is_admin, field_of_study, study_goal, preferred_engine, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        u = cursor.fetchone()

    if not u:
        raise ValueError("User not found.")

    public_id = u["public_id"] or f"COG-{100000 + u['id']}"

    # Fetch user study statistics from SQLite
    try:
        from sessions_db import get_study_analytics
        analytics = get_study_analytics(user_id=user_id)
    except Exception:
        analytics = {}

    return {
        "id": u["id"],
        "public_id": public_id,
        "name": u["name"],
        "email": u["email"],
        "is_admin": u["is_admin"] or 0,
        "field_of_study": u["field_of_study"] or "Computer Science & AI",
        "study_goal": u["study_goal"] or "Master high-yield concepts & active recall",
        "preferred_engine": u["preferred_engine"] or "auto",
        "created_at": u["created_at"],
        "stats": analytics
    }

def update_user_profile(
    user_id: int,
    name: Optional[str] = None,
    field_of_study: Optional[str] = None,
    study_goal: Optional[str] = None,
    preferred_engine: Optional[str] = None
) -> Dict[str, Any]:
    """Updates profile attributes for an authenticated user."""
    updates = []
    params = []

    if name and name.strip():
        updates.append("name = ?")
        params.append(name.strip())
    if field_of_study is not None:
        updates.append("field_of_study = ?")
        params.append(field_of_study.strip())
    if study_goal is not None:
        updates.append("study_goal = ?")
        params.append(study_goal.strip())
    if preferred_engine is not None:
        updates.append("preferred_engine = ?")
        params.append(preferred_engine.strip())

    if updates:
        params.append(user_id)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

    return get_user_profile(user_id)

def get_admin_dashboard_data() -> Dict[str, Any]:
    """
    Returns platform-wide metrics for the administrator console:
    - Total website visits & unique visitors
    - Total registered users count & directory list
    - Live login activity log (who logged in, user ID, email, timestamp)
    - Total global study sessions and inquiries
    """
    with get_db() as conn:
        cursor = conn.cursor()
        # Visit metrics
        cursor.execute("SELECT COUNT(*) as total_visits, COUNT(DISTINCT visitor_id) as unique_visitors FROM site_visits")
        visit_row = cursor.fetchone()
        total_visits = visit_row["total_visits"] if visit_row else 0
        unique_visitors = visit_row["unique_visitors"] if visit_row else 0

        # Total registered users
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()["total_users"]

        # All registered users list
        cursor.execute("""
            SELECT 
                u.id,
                u.public_id,
                u.name,
                u.email,
                u.is_admin,
                u.field_of_study,
                u.created_at,
                (SELECT COUNT(*) FROM study_sessions WHERE user_id = u.id) as sessions_count
            FROM users u
            ORDER BY u.id DESC
        """)
        user_rows = cursor.fetchall()

        # Recent logins (last 60)
        cursor.execute("""
            SELECT 
                l.id,
                l.user_id,
                l.email,
                l.auth_method,
                l.created_at,
                u.name,
                u.public_id
            FROM login_logs l
            LEFT JOIN users u ON l.user_id = u.id
            ORDER BY l.id DESC
            LIMIT 60
        """)
        login_rows = cursor.fetchall()

        # Global platform study count
        try:
            cursor.execute("SELECT COUNT(*) as total_sessions FROM study_sessions")
            total_sessions = cursor.fetchone()["total_sessions"]
            cursor.execute("SELECT COUNT(*) as total_queries FROM session_messages WHERE role = 'user'")
            total_queries = cursor.fetchone()["total_queries"]
        except Exception:
            total_sessions = 0
            total_queries = 0

    users_list = []
    for r in user_rows:
        pid = r["public_id"] or f"COG-{100000 + r['id']}"
        users_list.append({
            "id": r["id"],
            "public_id": pid,
            "name": r["name"],
            "email": r["email"],
            "is_admin": bool(r["is_admin"]),
            "field_of_study": r["field_of_study"] or "General Studies",
            "created_at": r["created_at"],
            "sessions_count": r["sessions_count"] or 0
        })

    logins_list = []
    for l in login_rows:
        pid = l["public_id"] or f"COG-{100000 + l['user_id']}"
        logins_list.append({
            "id": l["id"],
            "user_id": l["user_id"],
            "public_id": pid,
            "name": l["name"] or l["email"].split("@")[0],
            "email": l["email"],
            "auth_method": l["auth_method"] or "password",
            "created_at": l["created_at"]
        })

    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_queries": total_queries,
        "users": users_list,
        "recent_logins": logins_list
    }
