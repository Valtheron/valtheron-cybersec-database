#!/usr/bin/env python3
"""
threat_intel.py – Costraca custom tool
Passive threat intelligence and OSINT gathering.
No active scanning, no exploitation. Read-only, offline-first.
"""
import sys
import json
import socket
import hashlib
import ipaddress
import subprocess
from pathlib import Path
from datetime import datetime, timezone


# ─── Constants ───────────────────────────────────────────────────────────────

REPORT_DIR = Path("/a0/output")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Known malicious port associations (informational only)
SUSPICIOUS_PORTS = {
    4444: "Metasploit default listener",
    1337: "Common C2/backdoor",
    31337: "Back Orifice / EliteRAT",
    6667: "IRC (often used by botnets)",
    6697: "IRC over TLS",
    9001: "Tor relay default",
    9050: "Tor SOCKS proxy",
}

# File magic bytes for malware-relevant formats
MAGIC_SIGNATURES = {
    b"MZ":               "Windows PE executable",
    b"\x7fELF":          "Linux ELF binary",
    b"PK\x03\x04":       "ZIP archive (JAR, DOCX, XLSX…)",
    b"\xca\xfe\xba\xbe": "Java class file",
    b"#!/":              "Script (shebang)",
    b"#!":               "Script (shebang)",
    b"\\x4d\\x5a":       "Escaped PE (possible obfuscation)",
    b"%PDF":             "PDF document",
    b"Rar!":             "RAR archive",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_hostname(host: str) -> dict:
    """Passive DNS resolution."""
    result = {"input": host, "resolved": None, "error": None}
    try:
        addr = socket.getaddrinfo(host, None)
        ips = list({a[4][0] for a in addr})
        result["resolved"] = ips
    except socket.gaierror as e:
        result["error"] = str(e)
    return result


def classify_ip(ip_str: str) -> dict:
    """Classify IP address (private/public/loopback/multicast)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return {
            "ip": ip_str,
            "version": ip.version,
            "private": ip.is_private,
            "loopback": ip.is_loopback,
            "multicast": ip.is_multicast,
            "global": ip.is_global,
            "reserved": ip.is_reserved,
        }
    except ValueError as e:
        return {"ip": ip_str, "error": str(e)}


def hash_file(filepath: str) -> dict:
    """Generate MD5 / SHA1 / SHA256 hashes for IOC identification."""
    path = Path(filepath)
    if not path.is_file():
        return {"error": f"File not found: {filepath}"}

    h_md5    = hashlib.md5()
    h_sha1   = hashlib.sha1()
    h_sha256 = hashlib.sha256()
    size     = 0
    magic    = None

    try:
        with open(path, "rb") as f:
            first_chunk = True
            for chunk in iter(lambda: f.read(65536), b""):
                if first_chunk:
                    magic = _detect_magic(chunk[:8])
                    first_chunk = False
                h_md5.update(chunk)
                h_sha1.update(chunk)
                h_sha256.update(chunk)
                size += len(chunk)

        return {
            "path": filepath,
            "size_bytes": size,
            "md5": h_md5.hexdigest(),
            "sha1": h_sha1.hexdigest(),
            "sha256": h_sha256.hexdigest(),
            "file_type": magic,
        }
    except PermissionError:
        return {"path": filepath, "error": "Permission denied"}


def _detect_magic(header: bytes) -> str:
    for magic, label in MAGIC_SIGNATURES.items():
        if header.startswith(magic):
            return label
    return "Unknown / data"


def analyse_iocs(iocs: list[str]) -> list[dict]:
    """
    Analyse a list of IOCs (IPs, hostnames, file paths, hashes).
    Classifies and enriches each IOC passively.
    """
    results = []
    for ioc in iocs:
        entry = {"ioc": ioc, "type": None, "analysis": {}}

        # Detect type
        try:
            ipaddress.ip_address(ioc)
            entry["type"] = "ip"
            entry["analysis"] = classify_ip(ioc)
        except ValueError:
            pass

        if entry["type"] is None and Path(ioc).exists():
            entry["type"] = "file"
            entry["analysis"] = hash_file(ioc)

        if entry["type"] is None:
            # Assume hostname
            entry["type"] = "hostname"
            entry["analysis"] = resolve_hostname(ioc)

        results.append(entry)

    return results


def check_listening_ports() -> list[dict]:
    """
    List locally listening ports and flag suspicious ones.
    Passive – no connection attempts.
    """
    cmd = ["ss", "-tlnp"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().split("\n")[1:]  # skip header
    except Exception as e:
        return [{"error": str(e)}]

    findings = []
    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[3]
        port_str = local_addr.rsplit(":", 1)[-1]
        try:
            port = int(port_str)
        except ValueError:
            continue

        entry = {
            "local_address": local_addr,
            "port": port,
            "suspicious": port in SUSPICIOUS_PORTS,
            "note": SUSPICIOUS_PORTS.get(port, ""),
            "raw": line.strip(),
        }
        findings.append(entry)

    return findings


def generate_report(iocs: list[str] | None = None) -> dict:
    """Main entry point: run full passive TI sweep and return report."""
    timestamp = utcnow()
    report = {
        "generated_at": timestamp,
        "tool": "threat_intel.py (Costraca)",
        "mode": "passive",
    }

    if iocs:
        report["ioc_analysis"] = analyse_iocs(iocs)

    report["listening_ports"] = check_listening_ports()

    # Persist
    report_file = REPORT_DIR / f"threat_intel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    report["_saved_to"] = str(report_file)
    return report


# ─── CLI ─────────────────────────────────────────────────────────────────────

def usage():
    print(f"""Usage: {sys.argv[0]} [OPTIONS]

Options:
  --ioc <value>    IOC to analyse (IP, hostname, or file path). Repeatable.
  --ports          List and flag suspicious listening ports only.
  --hash <file>    Hash a single file and detect its type.
  --help           Show this help.

Examples:
  python3 threat_intel.py --ioc 185.220.101.1 --ioc evil.example.com
  python3 threat_intel.py --ports
  python3 threat_intel.py --hash /tmp/suspicious.bin
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args:
        usage()
        sys.exit(0)

    if "--hash" in args:
        idx = args.index("--hash")
        target = args[idx + 1] if idx + 1 < len(args) else None
        if not target:
            print("Error: --hash requires a file path.")
            sys.exit(1)
        print(json.dumps(hash_file(target), indent=2))
        sys.exit(0)

    if "--ports" in args:
        print(json.dumps(check_listening_ports(), indent=2))
        sys.exit(0)

    iocs = []
    i = 0
    while i < len(args):
        if args[i] == "--ioc" and i + 1 < len(args):
            iocs.append(args[i + 1])
            i += 2
        else:
            i += 1

    report = generate_report(iocs if iocs else None)
    print(json.dumps(report, indent=2))
