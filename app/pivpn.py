import subprocess
from pathlib import Path
from typing import List, Dict
import time

CONFIG_DIR = "/etc/wireguard/configs"
WG_CMD = ["sudo", "wg", "show"]  # tab-separated machine-readable output


# ---------------------- Helper functions ----------------------

def _human_bytes(n: int) -> str:
    """Convert bytes to human-readable format (B, KB, MB, GB)."""
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024.0
        if n < 1024.0:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"


def _read_client_address_map() -> Dict[str, str]:
    """
    Read each client .conf and build a mapping: {virtual_ip: client_name}.
    Looks for lines like: Address = 10.6.0.2/32
    """
    return
    mapping = {}
    cfg_dir = Path(CONFIG_DIR)
    if not cfg_dir.exists():
        return mapping

    for p in cfg_dir.glob("*.conf"):
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue

        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("address"):
                parts = line.replace(":", "=").split("=", 1)
                if len(parts) < 2:
                    continue
                addr = parts[1].strip().split()[0]
                ip = addr.split("/")[0]
                mapping[ip] = p.stem
                break

    return mapping


def get_total_clients() -> int:
    """Return total number of client config files (.conf)."""
    try:
        return len(list(Path(CONFIG_DIR).glob("*.conf")))
    except Exception:
        return 0


# ---------------------- Core WireGuard parser ----------------------

def get_connected_clients() -> List[Dict]:
    """
    Use `wg show` to list active peers and data usage.

    Returns a list of dicts:
    [
      {
        "name": "phone",
        "remote_ip": "12.34.56.78:51820",
        "virtual_ip": "10.6.0.2",
        "bytes_received": "5.23 MB",
        "bytes_sent": "8.14 MB",
        "rx_raw": 5481302,
        "tx_raw": 8532001,
        "last_seen": "3m ago",
        "connected": True
      }
    ]
    """
    clients = []
    ip_to_name = _read_client_address_map()

    # Call wg show (needs root)
    try:
        out = subprocess.check_output(WG_CMD, stderr=subprocess.STDOUT).decode(errors="ignore")
    except subprocess.CalledProcessError as e:
        print("wg command failed:", e)
        return clients
    except FileNotFoundError:
        print("wg tool not found (install wireguard-tools)")
        return clients

    # Each peer line: interface, public_key, preshared_key, endpoint, allowed_ips,
    # latest_handshake, transfer_rx, transfer_tx, persistent_keepalive
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            continue

        iface, pubkey, preshared, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx = parts[:8]

        # Parse allowed IP
        vip = None
        for a in allowed_ips.split(","):
            a = a.strip()
            if not a:
                continue
            if "/" in a:
                ip_only = a.split("/")[0]
            else:
                ip_only = a
            if ip_only.count(".") == 3:  # IPv4 only
                vip = ip_only
                break
        if not vip:
            continue

        # Map to config name
        name = ip_to_name.get(vip, vip)

        # Bytes
        try:
            rx = int(transfer_rx)
        except Exception:
            rx = 0
        try:
            tx = int(transfer_tx)
        except Exception:
            tx = 0

        # Handshake (epoch seconds)
        connected = False
        try:
            hs = int(latest_handshake)
            if hs > 0:
                connected = True
                age = time.time() - hs
                if age < 60:
                    last_seen = f"{int(age)}s ago"
                elif age < 3600:
                    last_seen = f"{int(age/60)}m ago"
                elif age < 86400:
                    last_seen = f"{int(age/3600)}h ago"
                else:
                    last_seen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(hs))
            else:
                last_seen = "offline"
        except Exception:
            last_seen = "unknown"

        clients.append({
            "name": name,
            "remote_ip": endpoint or "",
            "virtual_ip": vip,
            "bytes_received": _human_bytes(rx),
            "bytes_sent": _human_bytes(tx),
            "rx_raw": rx,
            "tx_raw": tx,
            "last_seen": last_seen,
            "connected": connected
        })

    return clients
    
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
