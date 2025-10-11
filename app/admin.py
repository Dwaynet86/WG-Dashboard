# app/admin.py
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import get_conn, upsert_user, get_user_role
from app.auth import get_username_from_request

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def require_admin(request: Request):
    username = get_username_from_request(request)
    if not username:
        return None
    role = get_user_role(username)
    return username if role == "admin" else None


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    user = require_admin(request)
    if not user:
        return RedirectResponse("/")
    conn = get_conn()
    users = conn.execute("SELECT username, role FROM users ORDER BY username").fetchall()
    conn.close()
    return templates.TemplateResponse("admin.html", {"request": request, "username": user, "users": users})


@router.post("/admin/add")
def add_user(request: Request, username: str = Form(...), role: str = Form(...)):
    user = require_admin(request)
    if not user:
        return RedirectResponse("/")
    upsert_user(username, role)
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/update")
def update_user(request: Request, username: str = Form(...), role: str = Form(...)):
    user = require_admin(request)
    if not user:
        return RedirectResponse("/")
    upsert_user(username, role)
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/delete")
def delete_user(request: Request, username: str = Form(...)):
    user = require_admin(request)
    if not user:
        return RedirectResponse("/")
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin", status_code=303)
