# Valtheron CyberSec AI Agent Stack

Local, offline, security-hardened AI agent setup for cybersecurity workflows.
100% private — no cloud, no API keys, full GPU acceleration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network (172.20.0.0/24)        │
│                                                          │
│  ┌─────────────┐   ┌──────────────┐  ┌──────────────┐  │
│  │   Ollama    │   │   Stopoda    │  │   Costraca   │  │
│  │ (GPU/CPU)   │◄──│ Primary Agent│  │Secondary Agent│  │
│  │ :11434      │   │ :8080        │  │ :8081        │  │
│  └──────┬──────┘   └──────────────┘  └──────────────┘  │
│         │                                               │
│  ┌──────┴──────┐   ┌──────────────┐                    │
│  │  Open-WebUI │   │  ChromaDB    │                    │
│  │  :3000      │   │  (RAG/Vector)│                    │
│  └─────────────┘   └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

| Service | Port | Purpose |
|---------|------|---------|
| Open-WebUI | 3000 | Shared chat interface for both models |
| Stopoda | 8080 | Primary agent (security analysis, scanning) |
| Costraca | 8081 | Secondary agent (backup, reporting, execution) |
| Ollama | 11434 | LLM backend (internal only) |
| ChromaDB | 8000 | Vector DB for RAG (internal only) |

## Models

| Agent | Model | Purpose |
|-------|-------|---------|
| Stopoda | `qwen2.5:7b-instruct-q5_K_S` | Best tool-calling + code reasoning |
| Costraca | `llama3.2:70b-instruct-q4_K_M` | General reasoning + report generation |
| Both | `nomic-embed-text` | Embeddings for RAG/memory |

## Quick Start

```bash
# 1. Clone and enter stack directory
cd ai-agent-stack

# 2. Run setup (installs deps, generates secrets, pulls models)
bash scripts/setup.sh

# 3. Apply security hardening (requires sudo)
sudo bash security/hardening.sh
```

### Clean Reinstall (removes everything)

```bash
bash scripts/cleanup.sh
```

## Security Hardening

The stack is hardened by default:

- **No `--privileged`** — capabilities dropped to minimum (`CHOWN`, `SETUID`, `SETGID` only)
- **Read-only tool mounts** — `./stopoda/tools` and `./costraca/tools` mounted `:ro`
- **cgroup limits** — 4 CPUs + 16 GB RAM per agent container
- **AppArmor profile** — `security/apparmor-agent.profile` restricts filesystem writes to `/a0/workspace` and `/a0/output` only
- **UFW rules** — WebUI ports (8080/8081/3000) localhost-only; Ollama/ChromaDB blocked externally
- **Secrets in `.env`** — auto-generated with `openssl rand -hex 32`; never committed to git
- **Human-in-loop** — agents ask for explicit confirmation before any destructive action

### What the agents CAN do
- Read files across the filesystem (read-only analysis)
- Execute allowed shell tools (find, grep, rsync --dry-run, etc.)
- Write to `/a0/workspace` and `/a0/output` only
- Use Python/Bash for data processing

### What the agents CANNOT do
- Write outside their workspace without confirmation
- Execute `rm -rf`, `mkfs`, `dd`, `fdisk`
- Open raw network sockets
- Load kernel modules
- Access `/etc/shadow`, `/etc/gshadow`

## Agent Tools

### Stopoda — Security Scanner

```bash
# Run from host to test the scanner tool
docker exec stopoda-agent python3 /a0/tools/security_scanner.py /home output.json
```

**Built-in prompt for security audit:**
> Scan directory recursively for sensitive files (`.pem`, `.key`, `.env`, SSH keys, etc.), classify by risk level (Critical/High/Medium/Low), generate backup plan, wait for confirmation before executing.

### Costraca — Backup Executor

```bash
# Dry run (safe preview)
docker exec costraca-agent python3 /a0/tools/backup_executor.py /a0/workspace/scan_output.json

# Execute backup (after dry-run review)
docker exec costraca-agent python3 /a0/tools/backup_executor.py /a0/workspace/scan_output.json --execute
```

## Multi-Agent Workflow Example

```
1. Stopoda (8080): "Run security_audit on /home and save results to /a0/workspace/audit.json"
   → Scans, classifies, outputs report, asks for confirmation

2. Costraca (8081): "Load /a0/workspace/audit.json, run backup dry-run, then ask for confirmation"
   → Validates plan, runs rsync --dry-run, shows results, waits

3. Human reviews → types "YES /backup/sensitive-files-2026-03-17"
   → Costraca executes real backup, generates checksums
```

## Recommended Test Prompts

**Stopoda — Security Audit:**
```
Security Audit Task (Step-by-Step with Safety):
1. Scan only (read-only): Search /home recursively for sensitive files matching:
   '*.pem', '*.key', '.ssh/', '.env', '*password*', '*secret*', '*.gpg'
   Ignore: .cache, Downloads, node_modules.
2. List in detail: Full path, size, last modified, first 50 bytes preview (no secrets).
3. Risk classification: low/medium/high (SSH keys=high, .env=high).
4. Backup plan: rsync --dry-run per category to /backup/sensitive/YYYY-MM-DD/.
5. Wait for confirmation: Output full report. Ask: "Confirm with YES + path or NO to abort."
Tools: shell (find/ls), file_manager (read-only). No sudo. No network.
```

**Costraca — Backup Execution:**
```
Backup Execution Task:
1. Load backup plan from /a0/workspace/backup_plan.json (generated by Stopoda).
2. Validate: confirm source paths exist and destination has enough space.
3. Dry run: rsync --dry-run --verbose for each item. Show full output.
4. Wait for confirmation before executing real backup.
5. On YES: execute, verify checksums, log to /a0/output/backup_TIMESTAMP.log.
```

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB+ |
| VRAM | 8 GB (quantized) | 24 GB (full precision) |
| GPU | RTX 30-series | RTX 40-series |
| Disk | 100 GB (models) | 200 GB+ |
| OS | Ubuntu 22.04 / WSL2 | Ubuntu 22.04 LTS |

## File Structure

```
ai-agent-stack/
├── docker-compose.yml          # Main stack definition
├── .env.example                # Template for secrets
├── .env                        # Your secrets (gitignored)
├── stopoda/
│   ├── agent_config.json       # Stopoda agent configuration
│   ├── tools/
│   │   └── security_scanner.py # Sensitive file scanner
│   ├── workspace/              # Agent working directory
│   └── output/                 # Reports and logs
├── costraca/
│   ├── agent_config.json       # Costraca agent configuration
│   ├── tools/
│   │   └── backup_executor.py  # Backup execution with dry-run
│   ├── workspace/
│   └── output/
├── security/
│   ├── hardening.sh            # UFW + AppArmor + permissions
│   └── apparmor-agent.profile  # AppArmor profile for agents
└── scripts/
    ├── setup.sh                # Full setup wizard
    └── cleanup.sh              # Full Docker cleanup
```
