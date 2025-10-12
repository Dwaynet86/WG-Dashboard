# app/pivpn.py
import subprocess, re
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

# app/pivpn.py (replace parse_pivpn_c_output with this)
import re
from typing import List, Dict

def parse_pivpn_c_output(raw: str) -> List[Dict]:
    """
    Robust parser for `pivpn -c` output.

    Strategy:
      - Skip obvious header/footer lines (those that start with ':::', 'Name', or separators).
      - Stop if we encounter '::: Disabled' (footer).
      - Use a regex to capture:
          group1: name (non-space)
          group2: remote ip (non-space)
          group3: virtual ip (non-space)
          group4: the rest of the line (bytes + last seen)
      - From group4, attempt to pull bytes received (first 1-2 tokens) and bytes sent (next 1-2 tokens),
        leaving the remainder as "last_seen".
    """
    clients = []
    if not raw:
        return clients

    # match first three whitespace-separated columns, rest captured as group 4
    row_re = re.compile(r'^(\S+)\s+(\S+)\s+(\S+)\s*(.*)$')

    lines = [l.rstrip() for l in raw.splitlines()]

    for line in lines:
        s = line.strip()
        if not s:
            continue
        # ignore header/footer lines
        if s.startswith(":::"):
            # Stop entirely if we hit disabled section
            if s.lower().startswith("::: disabled"):
                break
            continue
        if s.startswith("Name"):
            continue
        if s.startswith("---") or s.startswith("----"):
            continue

        m = row_re.match(s)
        if not m:
            # not a data row
            continue

        name, remote_ip, virtual_ip, rest = m.groups()
        # 'rest' normally contains: BytesReceivedBytesUnit [maybe two tokens], BytesSentBytesUnit, LastSeen...
        # Split rest into tokens and try to pick bytes fields heuristically.
        tokens = rest.split()
        bytes_rx = "0"
        bytes_tx = "0"
        last_seen = "-"

        # heuristics: bytes_rx often at tokens[0..1] (e.g., "12.3", "KB/MB" or "12.3KB"), bytes_tx next
        # We'll attempt several safe parses.
        try:
            if len(tokens) >= 2:
                # take first two as bytes_rx candidate (like "12.3" + "MB")
                bytes_rx = tokens[0] + ((" " + tokens[1]) if not tokens[1].upper().startswith(("KB","MB","GB")) else " " + tokens[1])
            elif len(tokens) >= 1:
                bytes_rx = tokens[0]

            # try to find bytes_tx after RX tokens: typically tokens[2:4]
            if len(tokens) >= 4:
                bytes_tx = tokens[2] + ((" " + tokens[3]) if not tokens[3].upper().startswith(("KB","MB","GB")) else " " + tokens[3])
                last_seen = " ".join(tokens[4:]) if len(tokens) > 4 else "-"
            elif len(tokens) == 3:
                bytes_tx = tokens[2]
                last_seen = "-"
            else:
                # fallback: remaining as last seen
                last_seen = " ".join(tokens[2:]) if len(tokens) > 2 else "-"
        except Exception:
            # any parsing problem -> keep defaults
            pass

        # final trim
        bytes_rx = bytes_rx.strip()
        bytes_tx = bytes_tx.strip()
        last_seen = last_seen.strip() if last_seen else "-"

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
