```markdown
# WG-Dashboard

WireGuard Web GUI — a web-based interface to manage WireGuard configurations.


Features
--------------------
- View WireGuard interface and peer status
- Create, edit and remove peers
- Generate keypairs and QR codes for client configs
- Import/export peer configs
- Apply/save configurations 
- Role-based access or basic admin authentication 
- REST API for automation 

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
bash run.sh
```

Configuration
-------------
- Default WireGuard interface: WG_INTERFACE (default: wg0)
- Path to WireGuard configuration files: /etc/wireguard (or configurable path)
- Admin credentials: environment variables or config file (ensure secure storage)
- TLS/HTTPS: For production, run behind a reverse proxy (nginx) with TLS or enable direct TLS support.


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


License
-------
This project is licensed under the MIT License. See LICENSE for details.

Contact
-------
Maintainer: Dwaynet86 (GitHub: https://github.com/Dwaynet86)
```
