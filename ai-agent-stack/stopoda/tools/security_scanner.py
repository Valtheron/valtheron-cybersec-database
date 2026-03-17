#!/usr/bin/env python3
"""
Stopoda Security Scanner Tool
Scans for sensitive files with risk classification - READ ONLY
"""

import os
import sys
import json
import hashlib
import stat
from pathlib import Path
from datetime import datetime
from typing import Optional

# Sensitive file patterns with risk levels
PATTERNS = {
    "critical": [
        "*.pem", "*.key", "*.p12", "*.pfx", "*.jks",
        "id_rsa", "id_ecdsa", "id_ed25519", "id_dsa",
        "*.kdbx",  # KeePass databases
    ],
    "high": [
        ".env", "*.env", ".env.*",
        "*password*", "*passwd*", "*secret*", "*credential*",
        "*.gpg", "*.asc",
        "config.json", "config.yaml", "config.yml",
        "secrets.json", "secrets.yaml",
    ],
    "medium": [
        "*.crt", "*.cer", "*.csr",
        "*.token", "*.apikey", "*.api_key",
        ".htpasswd", ".netrc", ".npmrc", ".pypirc",
        "terraform.tfstate", "*.tfvars",
    ],
    "low": [
        "*.log",
        "*.bak", "*.backup",
        "*.sql", "*.dump",
        "docker-compose.yml", "docker-compose.yaml",
    ]
}

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".cache",
    "Downloads", "Trash", ".local/share/Trash",
    "proc", "sys", "dev", "run"
}


def get_preview(filepath: Path, max_bytes: int = 50) -> str:
    """Get safe preview of file without exposing secrets."""
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(max_bytes)
        # Only show hex for files that might contain binary secrets
        if b'\x00' in raw:
            return f"[binary: {raw[:16].hex()}...]"
        text = raw.decode('utf-8', errors='replace')
        # Redact common secret patterns
        import re
        text = re.sub(r'(password|secret|key|token)\s*[=:]\s*\S+',
                      r'\1=***REDACTED***', text, flags=re.IGNORECASE)
        return text[:50].replace('\n', '\\n')
    except (PermissionError, OSError):
        return "[unreadable]"


def classify_risk(filepath: Path) -> Optional[str]:
    """Return risk level if file matches sensitive patterns, else None."""
    import fnmatch
    name = filepath.name
    for level, patterns in PATTERNS.items():
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(str(filepath), f"*/{pattern}"):
                return level
    return None


def scan_directory(target_dir: str, output_file: Optional[str] = None) -> dict:
    """Scan directory for sensitive files. Read-only operation."""
    target = Path(target_dir).resolve()
    if not target.exists():
        return {"error": f"Directory {target_dir} does not exist"}

    findings = {"critical": [], "high": [], "medium": [], "low": []}
    stats = {"scanned": 0, "skipped": 0, "errors": 0}

    print(f"[*] Scanning: {target} (READ-ONLY)")
    print(f"[*] Started: {datetime.now().isoformat()}\n")

    for dirpath, dirnames, filenames in os.walk(target):
        # Skip ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            stats["scanned"] += 1

            risk = classify_risk(filepath)
            if not risk:
                continue

            try:
                file_stat = filepath.stat()
                entry = {
                    "path": str(filepath),
                    "size_bytes": file_stat.st_size,
                    "size_human": f"{file_stat.st_size / 1024:.1f} KB",
                    "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    "permissions": oct(stat.S_IMODE(file_stat.st_mode)),
                    "risk": risk,
                    "preview": get_preview(filepath)
                }
                findings[risk].append(entry)
            except (PermissionError, OSError) as e:
                stats["errors"] += 1

    # Summary
    total_findings = sum(len(v) for v in findings.values())
    result = {
        "scan_info": {
            "target": str(target),
            "timestamp": datetime.now().isoformat(),
            "files_scanned": stats["scanned"],
            "total_findings": total_findings
        },
        "findings": findings,
        "backup_plan": _generate_backup_plan(findings, target)
    }

    # Print report
    print(f"{'='*60}")
    print(f"SCAN RESULTS - {target}")
    print(f"{'='*60}")
    print(f"Files scanned: {stats['scanned']}")
    print(f"Total findings: {total_findings}\n")

    for level in ["critical", "high", "medium", "low"]:
        items = findings[level]
        if not items:
            continue
        print(f"\n[{level.upper()}] - {len(items)} findings:")
        for item in items:
            print(f"  Path:     {item['path']}")
            print(f"  Size:     {item['size_human']}")
            print(f"  Modified: {item['last_modified']}")
            print(f"  Perms:    {item['permissions']}")
            print(f"  Preview:  {item['preview']}")
            print()

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n[*] Full results saved to: {output_file}")

    print(f"\n{'='*60}")
    print("BACKUP PLAN (dry-run commands):")
    print(f"{'='*60}")
    for cmd in result["backup_plan"]["rsync_commands"]:
        print(f"  {cmd}")

    print(f"\n[!] CONFIRM TO PROCEED:")
    print(f"    Type: YES + backup path to execute backup")
    print(f"    Type: NO to abort")

    return result


def _generate_backup_plan(findings: dict, base_path: Path) -> dict:
    """Generate rsync backup plan for found sensitive files."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_base = f"/backup/sensitive-files-{date_str}"
    commands = []

    for level in ["critical", "high", "medium"]:
        items = findings.get(level, [])
        if not items:
            continue
        dest = f"{backup_base}/{level}/"
        commands.append(f"mkdir -p {dest}")
        for item in items:
            commands.append(
                f"rsync --dry-run --verbose --checksum {item['path']} {dest}"
            )

    return {
        "backup_base": backup_base,
        "rsync_commands": commands,
        "note": "All commands shown are --dry-run. Remove --dry-run only after confirmation."
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/home"
    output = sys.argv[2] if len(sys.argv) > 2 else None
    scan_directory(target, output)
