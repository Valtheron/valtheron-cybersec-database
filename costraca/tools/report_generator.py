#!/usr/bin/env python3
"""
report_generator.py – Costraca custom tool
Aggregates JSON outputs from Stopoda + Costraca and produces a
structured Markdown report with SHA-256 integrity hash.
"""
import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone


OUTPUT_DIR = Path("/a0/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
    "info":     "⚪",
}


# ─── Collectors ──────────────────────────────────────────────────────────────

def collect_json_files(source_dir: Path) -> list[dict]:
    """Load all *.json files from source_dir recursively."""
    findings = []
    for p in sorted(source_dir.rglob("*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
            findings.append({"source_file": str(p), "data": data})
        except (json.JSONDecodeError, PermissionError) as e:
            findings.append({"source_file": str(p), "error": str(e)})
    return findings


def collect_log_summary(source_dir: Path) -> list[dict]:
    """Summarise *.log files: line count + last 5 lines each."""
    summaries = []
    for p in sorted(source_dir.rglob("*.log")):
        try:
            lines = p.read_text(errors="replace").splitlines()
            summaries.append({
                "log_file": str(p),
                "total_lines": len(lines),
                "tail": lines[-5:] if lines else [],
            })
        except PermissionError:
            summaries.append({"log_file": str(p), "error": "permission denied"})
    return summaries


# ─── Severity classification ─────────────────────────────────────────────────

def classify_finding(data: dict) -> str:
    """Best-effort severity detection from arbitrary JSON payloads."""
    # Direct severity field
    for key in ("severity", "risk", "level", "priority"):
        val = str(data.get(key, "")).lower()
        if val in SEVERITY_ORDER:
            return val

    # Nested: scan results with by_risk block
    if "by_risk" in data:
        if data["by_risk"].get("high", 0) > 0:
            return "high"
        if data["by_risk"].get("medium", 0) > 0:
            return "medium"
        return "low"

    return "info"


# ─── Markdown renderer ───────────────────────────────────────────────────────

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    sep = ["-" * max(len(h), 3) for h in headers]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def build_markdown(
    title: str,
    operator: str,
    json_findings: list[dict],
    log_summaries: list[dict],
    extra_notes: str = "",
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    by_severity: dict[str, list[dict]] = {s: [] for s in SEVERITY_ORDER}
    errors = []

    for item in json_findings:
        if "error" in item:
            errors.append(item)
        else:
            sev = classify_finding(item["data"])
            by_severity[sev].append(item)

    total = sum(len(v) for v in by_severity.values())

    lines = [
        f"# {title}",
        f"",
        f"**Generated:** {now}  ",
        f"**Operator:** {operator}  ",
        f"**Agent:** Costraca (Valtheron CyberSec Stack)  ",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"| Severity | Count |",
        f"|----------|-------|",
    ]

    for sev in SEVERITY_ORDER:
        emoji = SEVERITY_EMOJI[sev]
        cnt = len(by_severity[sev])
        lines.append(f"| {emoji} {sev.capitalize()} | {cnt} |")

    lines += [
        f"| **Total findings** | **{total}** |",
        f"",
    ]

    if extra_notes:
        lines += [f"### Notes", f"", extra_notes, f""]

    # Findings by severity
    lines += [f"---", f"", f"## Findings", f""]

    for sev in SEVERITY_ORDER:
        items = by_severity[sev]
        if not items:
            continue
        emoji = SEVERITY_EMOJI[sev]
        lines += [f"### {emoji} {sev.capitalize()} ({len(items)})", f""]

        rows = []
        for item in items:
            src = Path(item["source_file"]).name
            data = item["data"]

            # Try to extract meaningful columns
            summary = (
                data.get("description")
                or data.get("message")
                or data.get("scan_time")
                or data.get("generated_at")
                or json.dumps(data)[:120]
            )
            root = data.get("root") or data.get("target") or data.get("ioc") or "-"
            hits = (
                data.get("total_hits")
                or data.get("total_findings")
                or data.get("count")
                or "-"
            )
            rows.append([src, str(root)[:40], str(hits), str(summary)[:80]])

        lines.append(_md_table(["Source", "Target/Root", "Hits", "Summary"], rows))
        lines.append("")

    # Logs
    if log_summaries:
        lines += [f"---", f"", f"## Audit Log Summary", f""]
        for ls in log_summaries:
            if "error" in ls:
                lines.append(f"- `{ls['log_file']}` — _{ls['error']}_")
                continue
            lines.append(f"**`{Path(ls['log_file']).name}`** ({ls['total_lines']} lines)")
            if ls["tail"]:
                lines += ["```", *ls["tail"], "```", ""]

    # Errors
    if errors:
        lines += [f"---", f"", f"## Parse Errors", f""]
        for e in errors:
            lines.append(f"- `{e['source_file']}`: {e['error']}")
        lines.append("")

    lines += [f"---", f"", f"_Report generated by Costraca report\\_generator.py_"]

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def generate(
    source_dir: str,
    title: str = "Security Assessment Report",
    operator: str = "Valtheron",
    notes: str = "",
) -> str:
    src = Path(source_dir)
    if not src.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    json_findings = collect_json_files(src)
    log_summaries = collect_log_summary(src)

    md = build_markdown(title, operator, json_findings, log_summaries, notes)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"report_{timestamp}.md"
    out_path.write_text(md, encoding="utf-8")

    # Integrity hash
    sha256 = hashlib.sha256(md.encode()).hexdigest()
    hash_path = OUTPUT_DIR / f"report_{timestamp}.md.sha256"
    hash_path.write_text(f"{sha256}  report_{timestamp}.md\n")

    print(f"[+] Report saved:  {out_path}")
    print(f"[+] SHA-256:       {sha256}")
    print(f"[+] Hash file:     {hash_path}")
    return str(out_path)


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Costraca Report Generator – aggregates agent outputs into Markdown."
    )
    parser.add_argument(
        "source_dir",
        nargs="?",
        default="/a0/output",
        help="Directory containing JSON/log findings (default: /a0/output)",
    )
    parser.add_argument("--title", default="Security Assessment Report")
    parser.add_argument("--operator", default="Valtheron")
    parser.add_argument("--notes", default="", help="Free-text notes for Executive Summary")
    args = parser.parse_args()

    try:
        path = generate(args.source_dir, args.title, args.operator, args.notes)
        print(f"\n[+] Done: {path}")
    except FileNotFoundError as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        sys.exit(1)
