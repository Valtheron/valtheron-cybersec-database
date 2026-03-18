#!/usr/bin/env bash
# =============================================================================
# Valtheron CyberSec Stack – Root Setup Script
# Run from the repository root: bash setup.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[+]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
log_step()  { echo -e "${BLUE}[*]${NC} $*"; }
log_error() { echo -e "${RED}[-]${NC} $*"; exit 1; }

STACK_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$STACK_DIR"

check_deps() {
  log_step "Checking dependencies..."
  command -v docker &>/dev/null       || log_error "Docker not found. Install: sudo apt install docker.io"
  docker compose version &>/dev/null  || log_error "Docker Compose v2 not found. Install: sudo apt install docker-compose-plugin"

  if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    log_info "GPU: $GPU"
    if ! docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi &>/dev/null 2>&1; then
      log_warn "nvidia-container-toolkit not configured – CPU-only mode."
    fi
  else
    log_warn "No NVIDIA GPU detected – CPU mode (slower inference)."
  fi
  log_info "Dependencies OK."
}

setup_env() {
  log_step "Setting up .env..."
  if [[ ! -f ".env" ]]; then
    cp .env.example .env
    WEBUI_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change_this_secret_key_immediately/$WEBUI_KEY/" .env
    chmod 600 .env
    log_info ".env created with random WEBUI_SECRET_KEY."
    log_warn "Set STOPODA_PASSWORD and COSTRACA_PASSWORD in .env before starting!"
  else
    log_info ".env already exists – skipping."
  fi
}

create_workspaces() {
  log_step "Creating workspace directories..."
  for agent in stopoda costraca; do
    mkdir -p "$agent/workspace" "$agent/output" "$agent/knowledge"
    touch "$agent/output/audit.log"
  done
  log_info "Workspaces ready."
}

start_stack() {
  log_step "Starting Docker Compose stack..."
  docker compose pull --quiet
  docker compose up -d

  log_step "Waiting for Ollama to be ready (up to 60s)..."
  for i in {1..12}; do
    if docker exec ollama-shared curl -sf http://localhost:11434/api/tags &>/dev/null; then
      log_info "Ollama is ready."
      break
    fi
    [[ $i -eq 12 ]] && log_error "Ollama did not start. Check: docker logs ollama-shared"
    sleep 5
  done
}

pull_models() {
  log_step "Pulling LLM models (first run: 10-30 min)..."

  log_info "Pulling qwen2.5-coder:32b-instruct-q5_K_M (Stopoda primary)..."
  docker exec ollama-shared ollama pull qwen2.5-coder:32b-instruct-q5_K_M

  log_info "Pulling llama3.2:latest (Costraca)..."
  docker exec ollama-shared ollama pull llama3.2:latest

  log_info "Pulling nomic-embed-text (embeddings / RAG)..."
  docker exec ollama-shared ollama pull nomic-embed-text

  log_info "Models loaded:"
  docker exec ollama-shared ollama list
}

print_status() {
  echo ""
  echo "======================================================================"
  echo " Valtheron CyberSec Stack – Ready"
  echo "======================================================================"
  docker compose ps
  echo ""
  echo " Access:"
  echo "   Open-WebUI:     http://localhost:3000"
  echo "   Stopoda:        http://localhost:8080"
  echo "   Costraca:       http://localhost:8081"
  echo "   Ollama API:     http://localhost:11434"
  echo ""
  echo " Commands:"
  echo "   docker compose logs -f stopoda-agent   # Stopoda logs"
  echo "   docker compose logs -f costraca-agent  # Costraca logs"
  echo "   docker stats                           # Resource usage"
  echo ""
  echo " Security hardening (run as root after first start):"
  echo "   sudo bash ai-agent-stack/security/hardening.sh"
  echo "======================================================================"
}

log_info "Valtheron CyberSec Stack Setup"
check_deps
setup_env
create_workspaces
start_stack
pull_models
print_status
