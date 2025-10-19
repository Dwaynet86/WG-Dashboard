# app/auth.py
"""
App-managed authentication (SQLite + bcrypt via passlib).

Provides:
- create_user(username, password, role='viewer', email=None)
- verify_user(username, password) -> bool
- create_session_for_user(username) -> token
- get_username_from_request(request) -> username or None
- require_role(request, roles=('admin',)) -> username or None
- logout_token(token)
- change_password(username, new_password)
"""

import secrets
import time
from typing import Optional
from fastapi import Request
from passlib.context import CryptContext
from app.database import (
    get_conn,
    save_session,
    get_session,
    delete_session,
    upsert_user,
    get_user_role,
    get_user_by_username,
    set_user_password_hash,
)

# bcrypt context
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# session TTL (seconds) - optional usage if you want to expire sessions
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days


# ----------------------
# User & password helpers
# ----------------------
def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password_hash(password: str, hash_: str) -> bool:
    try:
        return pwd_ctx.verify(password, hash_)
    except Exception:
        return False


def create_user(username: str, password: str, role: str = "viewer", email: Optional[str] = None):
    """Create or update a user in users table with hashed password and role."""
    password_hash = hash_password(password)
    print("UserName:{username}, Role:{role}, Email:{email}, Password:{password_hash})

    upsert_user(username, role, email, password_hash)


def verify_user(username: str, password: str) -> bool:
    """Return True if user exists and password is valid."""
    user = get_user_by_username(username)
    if not user:
        return False
    stored_hash = user.get("password_hash")
    if not stored_hash:
        return False
    return verify_password_hash(password, stored_hash)


# ----------------------
# Session helpers
# ----------------------
def create_session_for_user(username: str) -> str:
    """
    Create a secure random session token, save to sessions table, and return it.
    """
    token = secrets.token_urlsafe(32)
    save_session(token, username)
    return token


def get_username_from_request(request: Request) -> Optional[str]:
    """
    Read session cookie and look up username from sessions table.
    """
    token = request.cookies.get("session")
    if not token:
        return None
    username = get_session(token)
    return username


def require_role(request: Request, roles=("admin", "viewer")) -> Optional[str]:
    """
    If the request has a valid logged-in user and that user's role is one of `roles`,
    return the username. Otherwise return None.
    """
    username = get_username_from_request(request)
    if not username:
        return None
    role = get_user_role(username)
    if role in roles:
        return username
    return None


def logout_token(token: str):
    delete_session(token)


# ----------------------
# Password management
# ----------------------
def change_password(username: str, new_password: str) -> bool:
    """Change a user's password (hash & store)."""
    try:
        new_hash = hash_password(new_password)
        set_user_password_hash(username, new_hash)
        return True
    except Exception:
        return False
