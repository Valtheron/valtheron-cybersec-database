"""
backup_helper.py – Stopoda custom tool
Safe backup utility: dry-run first, requires explicit human confirmation.
No destructive actions without JA confirmation.
"""
import os
import subprocess
import json
from pathlib import Path
from datetime import date


BACKUP_ROOT = Path("/backup/sensitive")


def build_backup_plan(scan_results: dict, backup_base: Path = BACKUP_ROOT) -> dict:
    """Build a backup plan grouped by risk level. Returns plan dict."""
    today = date.today().isoformat()
    target_dir = backup_base / today

    plan = {
        "target_directory": str(target_dir),
        "date": today,
        "groups": {},
    }

    for entry in scan_results.get("files", []):
        risk = entry["risk"]
        if risk not in plan["groups"]:
            plan["groups"][risk] = {"files": [], "archive": str(target_dir / f"{risk}-files.tar.gz")}
        plan["groups"][risk]["files"].append(entry["path"])

    return plan


def dry_run_backup(plan: dict) -> dict:
    """Run rsync --dry-run for each group. Returns dry-run output."""
    dry_results = {}
    for risk, group in plan["groups"].items():
        if not group["files"]:
            continue
        cmd = ["rsync", "--dry-run", "-av", "--files-from=-",
               "/", str(Path(plan["target_directory"]) / risk) + "/"]
        try:
            result = subprocess.run(
                cmd,
                input="\n".join(group["files"]),
                capture_output=True, text=True, timeout=30
            )
            dry_results[risk] = {
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:500],
                "returncode": result.returncode,
            }
        except FileNotFoundError:
            dry_results[risk] = {"error": "rsync not found – install via apt install rsync"}
        except subprocess.TimeoutExpired:
            dry_results[risk] = {"error": "rsync dry-run timed out"}
    return dry_results


def execute_backup(plan: dict, confirmation: str) -> dict:
    """
    Execute real backup ONLY if confirmation == 'JA'.
    Returns execution results.
    """
    if confirmation.strip().upper() != "JA":
        return {"status": "ABORTED", "reason": "Confirmation not received. Expected 'JA'."}

    target = Path(plan["target_directory"])
    target.mkdir(parents=True, exist_ok=True)

    results = {}
    for risk, group in plan["groups"].items():
        if not group["files"]:
            continue
        risk_dir = target / risk
        risk_dir.mkdir(exist_ok=True)
        archive = group["archive"]

        cmd = ["tar", "-czf", archive, "--files-from=/dev/stdin"]
        try:
            result = subprocess.run(
                cmd,
                input="\n".join(group["files"]),
                capture_output=True, text=True, timeout=120
            )
            results[risk] = {
                "archive": archive,
                "returncode": result.returncode,
                "stderr": result.stderr[:500],
            }
        except Exception as e:
            results[risk] = {"error": str(e)}

    return {"status": "EXECUTED", "results": results}


if __name__ == "__main__":
    # Demo: print a sample plan (no execution)
    sample = {"files": [
        {"path": "/home/user/.ssh/id_rsa", "risk": "high"},
        {"path": "/home/user/.env", "risk": "medium"},
    ]}
    plan = build_backup_plan(sample)
    print(json.dumps(plan, indent=2))
    print("\nDry-run results:")
    dry = dry_run_backup(plan)
    print(json.dumps(dry, indent=2))
