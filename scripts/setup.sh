#!/usr/bin/env bash
# ============================================================
# Valtheron CyberSec – Setup Script
# Installs prerequisites, pulls models, starts the stack.
# Run as regular user (with sudo rights), NOT as root.
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Verify not running as root ────────────────────────────────────────────
[[ $EUID -eq 0 ]] && error "Do NOT run as root. Use a user with sudo privileges."

# ── 2. System dependencies ───────────────────────────────────────────────────
info "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y docker.io docker-compose-plugin nvidia-container-toolkit \
     curl git rsync tar ufw 2>/dev/null || true

sudo nvidia-ctk runtime configure --runtime=docker 2>/dev/null || warn "NVIDIA CTK config skipped (no GPU?)"
sudo systemctl restart docker
sudo usermod -aG docker "$USER"

# ── 3. Verify Docker & GPU ───────────────────────────────────────────────────
info "Verifying Docker..."
docker run --rm hello-world >/dev/null 2>&1 && info "Docker OK" || error "Docker test failed"

info "Verifying NVIDIA GPU (optional)..."
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi 2>/dev/null \
  && info "NVIDIA GPU detected" || warn "No NVIDIA GPU detected – will run on CPU (slower)"

# ── 4. Create directory structure ────────────────────────────────────────────
info "Creating agent directories..."
mkdir -p stopoda/{tools,config} costorca/{tools,config}

# ── 5. Create .env from template ─────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  SECRET=$(openssl rand -hex 32)
  sed -i "s/replace-with-a-random-64-char-string/$SECRET/" .env
  warn ".env created. Set strong passwords in .env before exposing to network!"
fi

# ── 6. Firewall ──────────────────────────────────────────────────────────────
info "Configuring firewall (localhost-only for agent ports)..."
sudo ufw allow 22/tcp 2>/dev/null || true       # SSH
sudo ufw deny 8080/tcp 2>/dev/null || true      # Block external Stopoda
sudo ufw deny 8081/tcp 2>/dev/null || true      # Block external Costraca
sudo ufw deny 11434/tcp 2>/dev/null || true     # Block external Ollama
sudo ufw --force enable 2>/dev/null || true
info "Ports 8080/8081/11434 blocked externally. Access via localhost only."

# ── 7. Start the stack ───────────────────────────────────────────────────────
info "Starting Docker Compose stack..."
docker compose up -d

info "Waiting for Ollama to be ready..."
for i in {1..30}; do
  curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && break
  sleep 5
  echo -n "."
done
echo ""

# ── 8. Pull models ───────────────────────────────────────────────────────────
info "Pulling Ollama models (this may take 10-30 minutes)..."

info "Pulling qwen2.5-coder:32b-instruct-q5_K_M (Stopoda)..."
docker exec ollama-shared ollama pull qwen2.5-coder:32b-instruct-q5_K_M

info "Pulling llama3.2:latest (Costraca)..."
docker exec ollama-shared ollama pull llama3.2:latest

info "Pulling nomic-embed-text (embeddings/RAG)..."
docker exec ollama-shared ollama pull nomic-embed-text

docker exec ollama-shared ollama list

# ── 9. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}  Setup complete! Access your agents:${NC}"
echo -e "${GREEN}  Open-WebUI : http://localhost:3000${NC}"
echo -e "${GREEN}  Stopoda    : http://localhost:8080${NC}"
echo -e "${GREEN}  Costraca   : http://localhost:8081${NC}"
echo -e "${GREEN}  Ollama API : http://localhost:11434${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo ""
warn "Reminder: Change default passwords in .env and restart the stack!"
