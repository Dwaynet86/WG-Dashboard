# app/database.py
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "dashboard.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_conn_lock = threading.Lock()

def get_conn():
    # Simple SQLite connection helper (serializes access via connect & check_same_thread)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _conn_lock:
        conn = get_conn()
        cur = conn.cursor()
        # users: username -> role (admin / viewer)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            role TEXT NOT NULL
        )""")
        # sessions: simple token-based sessions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        # traffic log: per-client samples
        cur.execute("""
        CREATE TABLE IF NOT EXISTS traffic_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            ts DATETIME DEFAULT (datetime('now')),
            bytes_in INTEGER,
            bytes_out INTEGER
        )""")
        conn.commit()
        conn.close()

def upsert_user(username, role="viewer"):
    with _conn_lock:
        conn = get_conn()
        conn.execute("INSERT OR REPLACE INTO users(username, role) VALUES (?,?)", (username, role))
        conn.commit()
        conn.close()

def get_user_role(username):
    with _conn_lock:
        conn = get_conn()
        r = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        return r["role"] if r else None

def save_session(token, username):
    with _conn_lock:
        conn = get_conn()
        conn.execute("INSERT OR REPLACE INTO sessions(token, username) VALUES (?,?)", (token, username))
        conn.commit()
        conn.close()

def get_session(token):
    with _conn_lock:
        conn = get_conn()
        r = conn.execute("SELECT username FROM sessions WHERE token = ?", (token,)).fetchone()
        conn.close()
        return r["username"] if r else None

def delete_session(token):
    with _conn_lock:
        conn = get_conn()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()

def insert_traffic_sample(client_name, bytes_in, bytes_out):
    with _conn_lock:
        conn = get_conn()
        conn.execute("INSERT INTO traffic_log(client_name, bytes_in, bytes_out) VALUES (?,?,?)",
                     (client_name, int(bytes_in), int(bytes_out)))
        conn.commit()
        conn.close()

def query_traffic(client_name=None, hours=24):
    with _conn_lock:
        conn = get_conn()
        if client_name:
            rows = conn.execute(
                "SELECT ts, bytes_in, bytes_out FROM traffic_log WHERE client_name=? AND ts >= datetime('now','-? hour') ORDER BY ts",
                (client_name, str(hours))
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ts, client_name, bytes_in, bytes_out FROM traffic_log WHERE ts >= datetime('now','-? hour') ORDER BY ts",
                (str(hours),)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
