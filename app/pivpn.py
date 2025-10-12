import subprocess
from pathlib import Path
from typing import List, Dict
import time

CONFIG_DIR = "/etc/wireguard/configs"
WG_CMD = ["wg", "show", "all", "dump"]  # tab-separated machine-readable output


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
    Use `wg show all dump` to list active peers and data usage.

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

    # Call wg show all dump (needs root)
    try:
        out = subprocess.check_output(WG_CMD, stderr=subprocess.STDOU
