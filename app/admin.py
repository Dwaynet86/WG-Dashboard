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

@router.post("/admin/add", response_class=HTMLResponse)
def add_user(request: Request, username: str = Form(...), role: str = Form(...), create_system: str = Form(None)):
    user = require_admin(request)
    if not user:
        return RedirectResponse("/")

    import subprocess, secrets, string

    new_password = None
    if create_system:
        # Check if system user already exists
        check_cmd = ["id", username]
        exists = subprocess.run(check_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not exists:
            # Generate random password
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(12))

            try:
                subprocess.run(["sudo", "useradd", "-m", username], check=True)
                subprocess.run(["sudo", "chpasswd"], input=f"{username}:{new_password}".encode(), check=True)
            except subprocess.CalledProcessError as e:
                print("Error creating system user:", e)

    # Add to dashboard DB
    upsert_user(username, role)

    # Show confirmation and password (if created)
    conn = get_conn()
    users = conn.execute("SELECT username, role FROM users ORDER BY username").fetchall()
    conn.close()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "username": user,
        "users": users,
        "new_user": username,
        "password": new_password
    })




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
