```markdown
# WG-Dashboard

WireGuard Web GUI — a web-based interface to manage WireGuard peers and configurations.

Status
------
This repository currently contains a minimal README. The project is implemented in Python and is licensed under the MIT License.

Features (suggested)
--------------------
- View WireGuard interface and peer status
- Create, edit and remove peers
- Generate keypairs and QR codes for client configs
- Import/export peer configs
- Apply/save configurations to /etc/wireguard or custom path
- Role-based access or basic admin authentication (optional)
- REST API for automation (optional)

Requirements
------------
- Linux host with WireGuard installed (wg, wg-quick)
- Python 3.8+
- Root privileges or CAP_NET_ADMIN to apply WireGuard configuration
- Optional: Docker for containerized deployment

Quickstart (example)
--------------------
1. Clone the repository:
```bash
git clone https://github.com/Dwaynet86/WG-Dashboard.git
cd WG-Dashboard
```

2. (Optional) Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```
If `requirements.txt` is not present, add dependencies for your chosen web framework (Flask, FastAPI, etc.) and any WireGuard helpers.

4. Configure environment variables (example):
```bash
export WG_INTERFACE=wg0
export HOST=0.0.0.0
export PORT=8080
export ADMIN_USER=admin
export ADMIN_PASSWORD=changeme
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

5. Run the application (example WSGI command — adjust module name as needed):
```bash
# Replace `app:app` with your app module and callable
gunicorn app:app -w 4 -b ${HOST}:${PORT}
```

Configuration
-------------
- Default WireGuard interface: WG_INTERFACE (default: wg0)
- Path to WireGuard configuration files: /etc/wireguard (or configurable path)
- Admin credentials: environment variables or config file (ensure secure storage)
- TLS/HTTPS: For production, run behind a reverse proxy (nginx) with TLS or enable direct TLS support.

Docker (example)
----------------
Build:
```bash
docker build -t wg-dashboard:latest .
```

Run (container needs NET_ADMIN and access to /dev/net/tun):
```bash
docker run -d \
  --name wg-dashboard \
  --cap-add=NET_ADMIN \
  --device /dev/net/tun \
  -v /etc/wireguard:/etc/wireguard:rw \
  -e WG_INTERFACE=wg0 \
  -e ADMIN_USER=admin \
  -e ADMIN_PASSWORD=changeme \
  -p 8080:8080 \
  wg-dashboard:latest
```

Systemd unit (example)
----------------------
An example unit to run a WSGI server as a service:
```ini
[Unit]
Description=WG-Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wg-dashboard
Environment=WG_INTERFACE=wg0
ExecStart=/usr/bin/gunicorn app:app -w 4 -b 0.0.0.0:8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
Note: Running as root may be required to manage WireGuard; prefer granting minimal capabilities where possible.

Security
--------
- Managing WireGuard requires elevated privileges — design the service and deployment so that only trusted administrators can access the dashboard.
- Use HTTPS in production. Run behind a reverse proxy or provide TLS termination.
- Store admin credentials and secrets securely (avoid committing secrets to source control).
- Validate and sanitize uploaded/imported configs.

Recommended project layout (if not already present)
---------------------------------------------------
- README.md
- LICENSE (MIT)
- requirements.txt
- app/ or src/ — application package
- static/ — frontend assets (JS/CSS)
- templates/ — HTML templates if using server-side rendering
- docker/ or Dockerfile
- tests/ — unit/integration tests
- docs/ — additional documentation

Contributing
------------
- Fork the repository and open a pull request with minimal, focused changes.
- Add tests for new features and make sure existing tests pass.
- Follow a consistent code style (e.g., black/flake8).

Troubleshooting
---------------
- "Permission denied" when applying configs: ensure the service has NET_ADMIN capability or run as root.
- Device /dev/net/tun not found in container: ensure the host has tun enabled (modprobe tun) and the device is exposed to the container.

License
-------
This project is licensed under the MIT License. See LICENSE for details.

Contact
-------
Maintainer: Dwaynet86 (GitHub: https://github.com/Dwaynet86)
```
