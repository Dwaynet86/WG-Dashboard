# app/pivpn.py
import subprocess
from typing import List, Dict
from pathlib import Path

CONFIG_DIR = "/etc/wireguard/configs"

def get_total_clients() -> int:
    """Count total config files (not just lines in clients.txt)"""
    try:
        files = Path(CONFIG_DIR).glob("*.conf")
        return len(list(files))
    except Exception:
        return 0

def parse_pivpn_c_output(raw: str) -> List[Dict]:
    """Parse output of pivpn -c for connected clients"""
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    clients = []
    # Skip the first two header lines
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        remote_ip = parts[1]
        virtual_ip = parts[2]
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
    """Run pivpn -c and parse output"""
    try:
        out = subprocess.check_output(["sudo", "pivpn", "-c"], stderr=subprocess.STDOUT).decode()
        return parse_pivpn_c_output(out)
    except Exception as e:
        print("Error reading connected clients:", e)
        return []

# --- Config management functions ---

def list_configs() -> List[str]:
    """Return all config file names without extension"""
    return [p.stem for p in Path(CONFIG_DIR).glob("*.conf")]

def read_config(name: str) -> str:
    """Read a specific WireGuard client config"""
    path = Path(CONFIG_DIR) / f"{name}.conf"
    if not path.exists():
        return ""
    return path.read_text()

def delete_config(name: str) -> bool:
    """Delete a config file"""
    try:
        path = Path(CONFIG_DIR) / f"{name}.conf"
        path.unlink(missing_ok=True)
        return True
    except Exception as e:
        print("Delete error:", e)
        return False

def toggle_config(name: str, enable: bool) -> bool:
    """Enable or disable a config (rename to .disabled or .conf)"""
    try:
        conf = Path(CONFIG_DIR) / f"{name}.conf"
        disabled = Path(CONFIG_DIR) / f"{name}.disabled"
        if enable and disabled.exists():
            disabled.rename(conf)
        elif not enable and conf.exists():
            conf.rename(disabled)
        return True
    except Exception as e:
        print("Toggle error:", e)
        return False

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
