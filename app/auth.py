# app/auth.py
import pam
import secrets
from datetime import timedelta
from fastapi import Request
from app.database import save_session, get_session, delete_session, upsert_user, get_user_role

_pam = pam.pam()

def verify_system_user(username: str, password: str) -> bool:
    # Uses system PAM to validate credentials
    try:
        return _pam.authenticate(username, password)
    except Exception:
        return False

def create_session_for_user(username: str):
    token = secrets.token_hex(24)
    save_session(token, username)
    # ensure user has a role entry (default viewer)
    if not get_user_role(username):
        upsert_user(username, "viewer")
    return token

def get_username_from_request(request: Request):
    token = request.cookies.get("session")
    if not token:
        return None
    return get_session(token)

def require_role(request: Request, roles=("admin", "viewer")):
    username = get_username_from_request(request)
    if not username:
        return None
    role = get_user_role(username)
    if role in roles:
        return username
    return None

def logout_token(token: str):
    delete_session(token)
