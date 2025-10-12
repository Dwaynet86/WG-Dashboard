# app/main.py
from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
from app.database import init_db, query_traffic, get_conn, log_admin_action
from app.auth import verify_user, create_session_for_user, get_username_from_request, logout_token
from app.pivpn import get_connected_clients, get_total_clients, get_qr_png
from app.pivpn import list_configs, read_config, delete_config, toggle_config
from app.wsmanager import wsmanager
from app import admin
import subprocess

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
    from app.database import get_user_role
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

@app.post("/password", response_class=HTMLResponse)
async def password_post(request: Request, current: str = Form(...), new1: str = Form(...), new2: str = Form(...)):
    username = get_username_from_request(request)
    if not username:
        return RedirectResponse("/login")

    if new1 != new2:
        return templates.TemplateResponse("password.html", {
            "request": request, "message": "New passwords do not match.", "success": False
        })
    log_admin_action(username, "change_password", username, "self-service password change")

    # Verify current password via PAM
    import pam
    p = pam.pam()
    if not p.authenticate(username, current):
        return templates.TemplateResponse("password.html", {
            "request": request, "message": "Current password is incorrect.", "success": False
        })

    # Change password via chpasswd
    try:
        subprocess.run(["sudo", "chpasswd"], input=f"{username}:{new1}".encode(), check=True)
        message = "Password successfully changed."
        success = True
    except subprocess.CalledProcessError as e:
        message = "Password change failed."
        success = False

    return templates.TemplateResponse("password.html", {
        "request": request, "message": message, "success": success
    })

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

@app.get("/api/clients")
async def api_clients():
    """
    Return live WireGuard status summary.
    Includes total clients (by .conf count) and currently active peers.
    """
    connected_list = get_connected_clients()
    total = get_total_clients()

    # Connected count = active peers with last_seen != 'offline'
    active = [c for c in connected_list if c.get("connected")]

    return JSONResponse({
        "total": total,
        "connected": active
    })


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
    clients = get_connected_clients()
    total = get_total_clients()
    return {"total": total, "connected": len(clients), "list": clients}

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
