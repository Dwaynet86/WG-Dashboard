# app/pivpn.py
import subprocess
from typing import List, Dict
from pathlib import Path

# Path to clients list or where configs live; adjust to match your setup
CLIENTS_TXT = "/etc/wireguard/configs/clients.txt"
CONFIG_DIR = "/etc/wireguard/configs"

def get_total_clients() -> int:
    try:
        out = subprocess.check_output(["bash", "-c", f"grep -c '^[VE]' {CLIENTS_TXT} || echo 0"]).decode().strip()
        return int(out)
    except Exception:
        return 0

def parse_pivpn_c_output(raw: str) -> List[Dict]:
    lines = raw.strip().splitlines()
    if len(lines) < 3:
        return []
    clients = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        remote_ip = parts[1] if len(parts) > 1 else ""
        virtual_ip = parts[2] if len(parts) > 2 else ""
        bytes_rx = " ".join(parts[3:5]) if len(parts) > 4 else "0"
        bytes_tx = " ".join(parts[5:7]) if len(parts) > 6 else "0"
        last_seen = " ".join(parts[7:]) if len(parts) > 7 else "-"
        clients.append({
            "name": name,
            "remote_ip": remote_ip,
            "virtual_ip": virtual_ip,
            "bytes_received": bytes_rx,
            "bytes_sent": bytes_tx,
            "last_seen": last_seen
        })
    return clients

def get_connected_clients() -> List[Dict]:
    try:
        out = subprocess.check_output(["pivpn", "-c"], stderr=subprocess.STDOUT).decode()
        return parse_pivpn_c_output(out)
    except Exception:
        return []

def read_config(name: str) -> str:
    p = Path(CONFIG_DIR) / f"{name}.conf"
    if p.exists():
        return p.read_text()
    return ""

def get_qr_png(name: str):
    # returns raw png bytes by piping config into qrencode
    p = Path(CONFIG_DIR) / f"{name}.conf"
    if not p.exists():
        return None
    cmd = f"qrencode -o - -t PNG < {str(p)}"
    try:
        return subprocess.check_output(cmd, shell=True)
    except Exception:
        return None
