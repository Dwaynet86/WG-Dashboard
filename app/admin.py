# app/admin.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import get_conn, upsert_user, get_user_role, log_admin_action, get_admin_log
from app.auth import get_username_from_request, create_user
import subprocess, secrets, string, smtplib
from email.mime.text import MIMEText

router = APIRouter()
templates = Jinja2Templates(directory="templates")

SMTP_SERVER = "localhost"  # or your relay (e.g. smtp.gmail.com)
SMTP_PORT = 25
SMTP_FROM = "pivpn@local"

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
    users = conn.execute("SELECT username, role, email FROM users ORDER BY username").fetchall()
    conn.close()

    logs = get_admin_log(limit=10)
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "username": user,
        "users": users,
        "logs": logs,
        "password": None,
        "new_user": None
    })


@router.post("/admin/add_user", response_class=HTMLResponse)
def add_user(
    request: Request,
    username: str = Form(...),
    role: str = Form(...),
    email: str = Form(""),
    password: str = Form("")
):
    admin = require_admin(request) # If not an Admin exit
    if not admin:
        return RedirectResponse("/")
        
    new_password = None
    if password == "":  # did user enter a password?
        # Generate a random temporary password
        new_password = secrets.token_urlsafe(8)
        message = f"User: '{username}' added with password: {new_password}"    
        # Add dashboard user record with temp password
        create_user(username,password,role,email)
        print(f"New password generated: {new_password}")
    else:
        # Add dashboard user record
        message = f"User: '{username}' added with password: {password}"
        create_user(username,password,role,email)
        print(f"User password:{password}")
    # Log action
    log_admin_action(admin, "add_user", username, f"role={role}, email={email}")

    # Send email if address provided and password created
    if email and new_password:
        try:
            msg = MIMEText(
                f"Hello {username},\n\nYour WG Dashboard account has been created.\n"
                f"Temporary password: {new_password}\n"
                f"Please change it on first login.\n\n-- WG Dashboard"
            )
            msg["Subject"] = "Your WG Dashboard Account"
            msg["From"] = SMTP_FROM
            msg["To"] = email
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
                s.send_message(msg)
        except Exception as e:
            print("Email send failed:", e)

    # Reload admin page
    conn = get_conn()
    users = conn.execute("SELECT username, role, email FROM users ORDER BY username").fetchall()
    conn.close()
    logs = get_admin_log(limit=10)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "success": message,
        "username": admin,
        "users": users,
        "logs": logs,
        "new_user": username if new_password else None,
        "password": None
    })


@router.post("/admin/update")
def update_user(request: Request, username: str = Form(...), role: str = Form(...), email: str = Form("")):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse("/")
    conn = get_conn()
    conn.execute("UPDATE users SET role=?, email=? WHERE username=?", (role, email, username))
    conn.commit()
    conn.close()
    log_admin_action(admin, "update_user", username, f"role={role}, email={email}")
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/delete")
def delete_user(request: Request, username: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse("/")
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    log_admin_action(admin, "delete_user", username)
    return RedirectResponse("/admin", status_code=303)
