# app/pivpn.py
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import time

CONFIG_DIR = "/etc/wireguard/configs"
WG_CMD = ["wg", "show", "all", "dump"]  # requires wg (wireguard-tools)

# --- Helpers ---

def _human_bytes(n: int) -> str:
    """Human-friendly bytes (B, KB, MB, GB)"""
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024.0
        if n < 1024.0:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"

def _read_client_address_map() -> Dict[str, str]:
    """
    Read all client .conf files and map virtual IP (without mask) -> client name.
    Looks for lines like: Address = 10.6.0.2/32
    """
    mapping = {}
    cfg_dir = Path(CONFIG_DIR)
    if not cfg_dir.exists():
        return mapping
    for p in cfg_dir.glob("*.conf"):
        try:
            text = p.read_text()
        except Exception:
            continue
        # find "Address" line
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("address"):
                # format: Address = 10.6.0.2/32 or Address: 10.6.0.2/32
                parts = line.split("=", 1) if "=" in line else line.split(":", 1)
                if len(parts) < 2:
                    continue
                addr = parts[1].strip().split()[0]
                ip = addr.split("/")[0]
                mapping[ip] = p.stem
                break
    return mapping

def get_total_clients() -> int:
    """Count .conf files in config dir"""
    try:
        return len(list(Path(CONFIG_DIR).glob("*.conf")))
    except Exception:
        return 0

# --- Main: parse wg show all dump ---

def get_connected_clients() -> List[Dict]:
    """
    Parse 'wg show all dump' and return list of connected peers with fields:
    name, remote_ip (endpoint), virtual_ip (allowed ip), bytes_received, bytes_sent, last_seen
    """
    clients = []
    ip_to_name = _read_client_address_map()

    # run wg
    try:
        out = subprocess.check_output(WG_CMD, stderr=subprocess.STDOUT).decode(errors="ignore")
    except subprocess.CalledProcessError as e:
        # if wg isn't available or permission denied, return empty
        print("wg command failed:", e)
        return clients
    except FileNotFoundError:
        print("wg tool not found")
        return clients

    # wg show all dump is tab-separated; each peer row looks like:
    # interface\tpublic_key\tpreshared_key\tendpoint\tallowed_ips\tlatest_handshake\ttransfer_rx\ttransfer_tx\tpersistent_keepalive
    # There may also be interface-specific header lines; we only process lines with >=8 fields.
    for raw_line in out.splitlines():
        if not raw_line.strip():
            continue
        cols = raw_line.split("\t")
        # we only care about peer lines with at least 8 columns (some versions)
        if len(cols) < 8:
            continue

        iface = cols[0]
        public_key = cols[1]
        # cols[2] preshared key (can be empty)
        endpoint = cols[3]  # "<ip>:<port>" or empty
        allowed_ips = cols[4]  # may contain comma-separated addresses
        latest_handshake = cols[5]
        transfer_rx = cols[6]
        transfer_tx = cols[7]

        # allowed_ips may include multiple addresses; choose first IPv4 /32 if present
        vip = None
        for part in allowed_ips.split(","):
            p = part.strip()
            if not p:
                continue
            # skip ranges or 0.0.0.0/0
            if "/" in p:
                ip_only = p.split("/")[0]
            else:
                ip_only = p
            # simple IPv4 check
            if ip_only.count(".") == 3:
                vip = ip_only
                break
        if not vip:
            # no usable virtual ip to map -> skip (likely not a client)
            continue

        name = ip_to_name.get(vip)  # may be None if no matching conf
        # interpret latest_handshake: usually '0' or epoch seconds (or '-' depending)
        try:
            hs = int(latest_handshake)
            if hs == 0:
                last_seen = "offline"
            else:
                # produce human-friendly relative time or timestamp
                dt = time.time() - hs
                if dt < 60:
                    last_seen = f"{int(dt)}s ago"
                elif dt < 3600:
                    last_seen = f"{int(dt/60)}m ago"
                elif dt < 86400:
                    last_seen = f"{int(dt/3600)}h ago"
                else:
                    last_seen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(hs))
        except Exception:
            last_seen = str(latest_handshake)

        try:
            rx = int(transfer_rx)
        except Exception:
            rx = 0
        try:
            tx = int(transfer_tx)
        except Exception:
            tx = 0

        clients.append({
            "name": name or vip,
            "remote_ip": endpoint or "",
            "virtual_ip": vip,
            "bytes_received": _human_bytes(rx),
            "bytes_sent": _human_bytes(tx),
            "last_seen": last_seen,
            "interface": iface,
            "public_key": public_key
        })

    # Optionally filter to only 'connected' where last_seen != 'offline'
    # But for dashboard, you may want all peers seen; choose to return all and let front-end decide
    return clients
