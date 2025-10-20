# app/main.py
from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, Response, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
from app.database import init_db, query_traffic, get_conn, log_admin_action, get_user_role, get_admin_log
from app.auth import verify_user, create_session_for_user, get_username_from_request, logout_token, change_password
from app.admin import require_admin
from app.pivpn import get_connected_clients, get_total_clients, get_qr_png
from app.pivpn import list_configs, read_config, delete_config, toggle_config
from app.wsmanager import wsmanager
from app import admin
import subprocess, secrets

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(admin.router)


# Initialize DB
init_db()

@app.on_event("startup")
async def startup_event():
    await wsmanager.start()

@app.on_event("shutdown")
async def shutdown_event():
    await wsmanager.stop()

# --------------------
# Pages & Auth
# --------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    username = get_username_from_request(request)
    if not username:
        return RedirectResponse("/login")
    role = None
    # role lookup via database (optional)
    
    role = get_user_role(username)
    return templates.TemplateResponse("index.html", {"request": request, "username": username, "role": role})

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login")
async def login_post(response: Response, username: str = Form(...), password: str = Form(...)):
    if verify_user(username, password):
        token = create_session_for_user(username)
        res = RedirectResponse("/", status_code=303)
        # set cookie secure flags
        res.set_cookie(key="session", value=token, httponly=True, samesite="Lax")  # add secure=True if using HTTPS
        return res
    # invalid
    return templates.TemplateResponse("login.html", {"request": {}, "error": "Invalid credentials"})

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        logout_token(token)
    r = RedirectResponse("/login")
    r.delete_cookie("session")
    return r

@app.get("/password", response_class=HTMLResponse)
async def password_get(request: Request):
    username = get_username_from_request(request)
    if not username:
        return RedirectResponse("/login")
    return templates.TemplateResponse("password.html", {"request": request, "message": None, "success": False})

@app.get("/change-password")
async def change_password_form(request: Request):
    username = get_username_from_request(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("change_password.html", {"request": request, "username": username})


@app.post("/change-password")
async def change_password_submit(request: Request, current_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...)):
    username = get_username_from_request(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    # Verify current password
    if not verify_user(username, current_password):
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "username": username, "error": "Current password is incorrect."},
        )

    # Validate new passwords match
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "username": username, "error": "New passwords do not match."},
        )

    # Update the password
    if change_password(username, new_password):
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "username": username, "success": "Password changed successfully."},
        )
    else:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "username": username, "error": "Failed to change password."},
        )

@app.post("/admin/reset-password")
async def admin_reset_password(request: Request, username: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse("/")
    
    conn = get_conn()
    users = conn.execute("SELECT username, role, email FROM users ORDER BY username").fetchall()
    conn.close()
    
    logs = get_admin_log(limit=30)
    
    # Generate a random temporary password
    temp_pass = secrets.token_urlsafe(8)
    if change_password(username, temp_pass):
        message = f"Password for '{username}' reset to: {temp_pass}"
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "success": message,                
                "username": admin,
                "users": users,
                "logs": logs,
                "password": None,
                "new_user": None
            },
        )
    else:
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "error": f"Failed to reset password for {username}.",
                "username": admin,
                "users": users,
                "logs": logs,
                "password": None,
                "new_user": None
                
            },
        )

# Add a new client configuration
@app.post("/admin/add_client")
async def add_client(request: Request,
                     client_name: str = Form(...),
                     username: str = Form(None),
                     link_user: str = Form(None),
                     ip: str = Form(None)
                    ):
                     
    current_user = get_username_from_request(request)
    role = get_user_role(current_user)
    
    # Only admin can add a new client
    if role != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    print("client:", client_name, "username:", username, "linkuser:", link_user, "ip:", ip)
    # call pivpn add
    if ip: # if no ip enetered use next available
        print(f"pivpn -a -n {client_name} -client-ip auto")
        #proc = subprocess.run(["pivpn", "-a", "-n", client_name, "-ip", "auto"], capture_output=True, text=True, timeout=10)
    else: # if ip enetered use it
       print(f"pivpn -a -n {client_name} -ip {ip}")
       #proc = subprocess.run(["pivpn", "-a", "-n", client_name, "-ip", ip], capture_output=True, text=True, timeout=10) 
    
    #if proc.returncode != 0:
    #    return JSONResponse({"error": "Failed to add client", "details": proc.stderr}, status_code=500)
   
    # Link to user if provided
    conn = get_conn()
    if link_user:
        conn.execute(
            "INSERT INTO clients (name, user_id) VALUES (?, (SELECT id FROM users WHERE username=?))",
            (client_name, link_user),
        )
    else:
        conn.execute("INSERT INTO clients (name) VALUES (?)", (client_name,))
    conn.commit()
    conn.close()

    return JSONResponse({"success": True})

@app.get("/api/configs")
async def api_configs():
    """Return a list of all client configs"""
    return {"configs": list_configs()}

@app.get("/api/config/{name}", response_class=PlainTextResponse)
async def api_config(name: str):
    """Show config text"""
    conf = read_config(name)
    if not conf:
        return PlainTextResponse("Config not found", status_code=404)
    return PlainTextResponse(conf, media_type="text/plain")

@app.get("/api/config/{name}/download")
async def api_download_config(name: str):
    """Download config"""
    conf = read_config(name)
    if not conf:
        return PlainTextResponse("Config not found", status_code=404)
    headers = {"Content-Disposition": f"attachment; filename={name}.conf"}
    return PlainTextResponse(conf, headers=headers, media_type="text/plain")

@app.delete("/api/config/{name}")
async def api_delete_config(name: str):
    """Delete config file"""
    ok = delete_config(name)
    return {"deleted": ok}

@app.post("/api/config/{name}/toggle")
async def api_toggle_config(name: str, enable: bool = Form(...)):
    """Enable or disable config file"""
    ok = toggle_config(name, enable)
    return {"ok": ok}


# --------------------
# WebSocket endpoint
# --------------------
@app.websocket("/ws/clients")
async def websocket_endpoint(websocket: WebSocket):
    await wsmanager.connect(websocket)
    try:
        while True:
            # The wsmanager will push broadcasts; keep the connection alive by consuming messages
            data = await websocket.receive_text()
            # optionally process client messages; currently ignore (heartbeat)
    except WebSocketDisconnect:
        wsmanager.disconnect(websocket)

# --------------------
# REST endpoints
# --------------------
@app.get("/api/clients")
async def api_clients():
    clients = get_connected_clients() # contains array of client configs
    total = get_total_clients() # contains the total number of config files
    active = [c for c in clients if c.get("connected")] # contans array the active clients
    return {"total": total, "connected": active, "clients": clients}

@app.get("/api/traffic/{client_name}")
async def api_traffic(client_name: str, hours: int = 24):
    rows = query_traffic(client_name=client_name, hours=hours)
    return {"client": client_name, "hours": hours, "rows": rows}

@app.get("/api/client/{name}/qr")
async def api_client_qr(name: str):
    png = get_qr_png(name)
    if png is None:
        return HTMLResponse("Not found", status_code=404)
    return StreamingResponse(iter([png]), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
