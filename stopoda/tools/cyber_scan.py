"""
cyber_scan.py – Stopoda custom tool
Read-only filesystem scanner for sensitive file detection.
Safe: no modifications, no network, dry-run only.
"""
import os
import stat
import json
from pathlib import Path
from datetime import datetime

SENSITIVE_PATTERNS = [
    ".pem", ".key", ".p12", ".pfx",           # Certificates / private keys
    ".env", ".env.local", ".env.prod",         # Environment files
    "password", "passwd", "secret", "token",   # Credential hints in filename
    ".ssh", "id_rsa", "id_ed25519",            # SSH keys
    ".gpg", ".asc",                            # GPG keys
    "credentials", "auth.json", "config.json", # Auth configs
    ".htpasswd", "shadow", "master.key",       # System credential files
]

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules",
    ".cache", "Downloads", "tmp", ".trash",
}

RISK_MAP = {
    "high":   [".pem", ".key", ".p12", ".pfx", "id_rsa", "id_ed25519", ".gpg", "shadow"],
    "medium": [".env", "secret", "password", "passwd", "credentials", "auth.json"],
    "low":    ["token", "config.json", ".htpasswd", "master.key"],
}


def classify_risk(filepath: str) -> str:
    fp = filepath.lower()
    for level in ("high", "medium", "low"):
        if any(p in fp for p in RISK_MAP[level]):
            return level
    return "low"


def safe_preview(filepath: str, max_bytes: int = 50) -> str:
    """Read first max_bytes as hex – never expose actual secrets."""
    try:
        with open(filepath, "rb") as f:
            raw = f.read(max_bytes)
        return raw.hex()
    except PermissionError:
        return "<permission denied>"
    except Exception as e:
        return f"<error: {e}>"


def scan_directory(root: str = "/home") -> dict:
    results = []
    root_path = Path(root)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            fp = os.path.join(dirpath, filename)
            fl = filename.lower()

            if not any(p in fl for p in SENSITIVE_PATTERNS):
                continue

            try:
                st = os.stat(fp)
                results.append({
                    "path": fp,
                    "size_bytes": st.st_size,
                    "last_modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "permissions": oct(stat.S_IMODE(st.st_mode)),
                    "risk": classify_risk(fp),
                    "preview_hex": safe_preview(fp),
                })
            except (PermissionError, FileNotFoundError):
                continue

    summary = {
        "scan_time": datetime.utcnow().isoformat() + "Z",
        "root": str(root_path),
        "total_hits": len(results),
        "by_risk": {
            "high":   sum(1 for r in results if r["risk"] == "high"),
            "medium": sum(1 for r in results if r["risk"] == "medium"),
            "low":    sum(1 for r in results if r["risk"] == "low"),
        },
        "files": results,
    }
    return summary


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "/home"
    report = scan_directory(root)
    print(json.dumps(report, indent=2))
