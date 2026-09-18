import os
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cognify.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
        conn.commit()

# Initialize tables immediately upon module load
init_db()

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

def register_user(name: str, email: str, password: str) -> dict:
    """Registers a new user account and returns the profile and session token."""
    clean_name = name.strip()
    clean_email = email.strip().lower()

    if not clean_name or len(clean_name) < 2:
        raise ValueError("Name must be at least 2 characters long.")
    if not clean_email or "@" not in clean_email:
        raise ValueError("Please provide a valid email address.")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    pwd_hash, salt = hash_password(password)

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                (clean_name, clean_email, pwd_hash, salt)
            )
            user_id = cursor.lastrowid
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")

    token = create_session(user_id)
    return {
        "user": {
            "id": user_id,
            "name": clean_name,
            "email": clean_email
        },
        "token": token
    }

def login_user(email: str, password: str) -> dict:
    """Authenticates a user with email and password."""
    clean_email = email.strip().lower()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, email, password_hash, salt FROM users WHERE email = ?",
            (clean_email,)
        )
        row = cursor.fetchone()

    if not row:
        raise ValueError("Invalid email or password.")

    if not verify_password(password, row["salt"], row["password_hash"]):
        raise ValueError("Invalid email or password.")

    token = create_session(row["id"])
    return {
        "user": {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"]
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
            SELECT u.id, u.name, u.email, u.created_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, now_iso))
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
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
