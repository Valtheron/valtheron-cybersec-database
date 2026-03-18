# Valtheron CyberSec – Local LLM Security Agent Stack

Vollständig offline, privat und dockerisiert. Kein Cloud, keine API-Kosten.

## Stack

| Dienst | Port | Beschreibung |
|---|---|---|
| **Ollama** | 11434 | LLM Backend (GPU-shared) |
| **Open-WebUI** | 3000 | Chat-Interface für beide Agenten |
| **Stopoda** | 8080 | Agent Zero – Coding, Recon, File Analysis |
| **Costraca** | 8081 | Agent Zero – Threat Intel, Reporting, Koordination |

## Modelle

| Agent | Modell | Stärke |
|---|---|---|
| Stopoda | `qwen2.5:7b-instruct-q5_K_S` | Code, Tool-Calling, Autonomie |
| Costraca | `llama3.2:latest` | Analyse, Reasoning, großer Kontext |
| Shared | `nomic-embed-text` | RAG / Vektordatenbank |

## Schnellstart

```bash
# 1. Repo klonen / in Verzeichnis wechseln
cd valtheron-cybersec-database

# 2. Setup ausführen (einmalig, ~30-45 Minuten)
./scripts/setup.sh

# 3. Stack starten
docker compose up -d

# 4. Logs prüfen
docker compose logs -f
```

## Agenten-URLs (nach Start)

- Open-WebUI: http://localhost:3000
- Stopoda:     http://localhost:8080
- Costraca:    http://localhost:8081

## Verzeichnisstruktur

```
.
├── docker-compose.yml          # Hauptkonfiguration
├── .env.example                # Umgebungsvariablen-Template
├── stopoda/
│   ├── config/agent.yaml       # Stopoda-Konfiguration
│   └── tools/
│       ├── cyber_scan.py       # Sensible-Files-Scanner (read-only)
│       └── backup_helper.py    # Backup-Tool mit dry-run + Bestätigung
├── costorca/
│   ├── config/agent.yaml       # Costraca-Konfiguration
│   └── tools/                  # Custom Tools hier einfügen
├── prompts/
│   ├── security_audit_backup.md     # Security Audit Prompt (ReAct)
│   └── multi_agent_coordination.md  # Multi-Agent Prompts
└── scripts/
    ├── setup.sh                # Ersteinrichtung
    └── cleanup.sh              # Vollständige Bereinigung
```

## Hardware-Anforderungen

| Konfiguration | RAM | GPU | Modell |
|---|---|---|---|
| Minimal | 16 GB | CPU only | llama3.2:8b |
| Empfohlen | 32 GB | RTX 3090/4090 (24 GB VRAM) | qwen2.5:7b-instruct-q5_K_S |
| Server | 64 GB+ | A100/H100 | 70B-Modelle |

## Security Hardening

- Kein `privileged: true` in Docker
- Ressourcen-Limits per Agent (4 CPUs, 16 GB RAM)
- Ports 8080/8081/11434 via UFW extern gesperrt
- Read-only Tool-Mounts (`:ro`)
- `confirm_human: true` in allen Agent-Configs
- Alle destruktiven Befehle in Blockliste

## Cleanup

```bash
./scripts/cleanup.sh
# Typ 'CLEANUP' zur Bestätigung
```
