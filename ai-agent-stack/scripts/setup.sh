#!/usr/bin/env bash
# =============================================================================
# Valtheron CyberSec AI Stack - Setup Script
# Installs dependencies, pulls models, starts all services
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[+]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
log_step()  { echo -e "${BLUE}[*]${NC} $*"; }
log_error() { echo -e "${RED}[-]${NC} $*"; exit 1; }

STACK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STACK_DIR"

# --- Checks ---
check_deps() {
  log_step "Checking dependencies..."

  command -v docker &>/dev/null        || log_error "Docker not found. Install: sudo apt install docker.io"
  docker compose version &>/dev/null   || log_error "Docker Compose v2 not found. Install: sudo apt install docker-compose-plugin"

  # NVIDIA check (optional)
  if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    log_info "GPU detected: $GPU"
    if ! docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi &>/dev/null 2>&1; then
      log_warn "nvidia-container-toolkit not configured. CPU-only mode."
      log_warn "Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    fi
  else
    log_warn "No NVIDIA GPU detected. Running in CPU mode (slower)."
  fi

  log_info "Dependencies OK."
}

# --- .env Setup ---
setup_env() {
  log_step "Setting up .env..."
  if [[ ! -f ".env" ]]; then
    cp .env.example .env
    # Generate random secrets
    WEBUI_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    CHROMA_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change_this_secret_key_immediately/$WEBUI_KEY/" .env
    sed -i "s/change_this_token/$CHROMA_KEY/" .env
    chmod 600 .env
    log_info ".env created with random secrets."
  else
    log_info ".env already exists."
  fi
}

# --- Workspace Dirs ---
create_workspaces() {
  log_step "Creating workspace directories..."
  for agent in stopoda costraca; do
    mkdir -p "$agent/workspace" "$agent/output" "$agent/knowledge"
    touch "$agent/output/audit.log"
  done
  log_info "Workspaces created."
}

# --- Start Stack ---
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
    [[ $i -eq 12 ]] && log_error "Ollama did not start in time. Check: docker logs ollama-shared"
    sleep 5
  done
}

# --- Pull Models ---
pull_models() {
  log_step "Pulling LLM models (this may take 10-30 min on first run)..."

  # Primary model for Stopoda
  log_info "Pulling qwen2.5:7b-instruct-q5_K_S (Stopoda)..."
  docker exec ollama-shared ollama pull qwen2.5:7b-instruct-q5_K_S

  # Secondary model for Costraca
  log_info "Pulling llama3.2:70b-instruct-q4_K_M (Costraca)... [optional, large]"
  read -r -p "  Pull 70B model? Requires ~40GB disk [y/N]: " yn
  if [[ "${yn,,}" == "y" ]]; then
    docker exec ollama-shared ollama pull llama3.2:70b-instruct-q4_K_M
  else
    log_warn "Skipping 70B model. Costraca will use qwen2.5:7b-instruct-q5_K_S instead."
    # Update costraca config to use same model
    if command -v jq &>/dev/null; then
      jq '.llm.model = "qwen2.5:7b-instruct-q5_K_S"' costraca/agent_config.json > /tmp/cfg.json
      mv /tmp/cfg.json costraca/agent_config.json
    fi
  fi

  # Embedding model for RAG
  log_info "Pulling nomic-embed-text (embeddings/RAG)..."
  docker exec ollama-shared ollama pull nomic-embed-text

  log_info "Models ready:"
  docker exec ollama-shared ollama list
}

# --- Status ---
print_status() {
  echo ""
  echo "======================================================================"
  echo " Valtheron CyberSec AI Stack - Status"
  echo "======================================================================"
  docker compose ps
  echo ""
  echo " Access Points:"
  echo "   Open-WebUI (shared chat):  http://localhost:3000"
  echo "   Stopoda agent WebUI:       http://localhost:8080"
  echo "   Costraca agent WebUI:      http://localhost:8081"
  echo "   Ollama API (internal):     http://localhost:11434"
  echo ""
  echo " Useful commands:"
  echo "   docker compose logs -f                    # Follow all logs"
  echo "   docker compose logs -f stopoda-agent      # Stopoda logs"
  echo "   docker stats                              # Resource usage"
  echo "   docker exec -it ollama-shared ollama list # List models"
  echo ""
  echo " Security hardening (run as root):"
  echo "   sudo bash security/hardening.sh"
  echo "======================================================================"
}

# --- Main ---
log_info "Valtheron CyberSec AI Stack Setup"
log_warn "Ensure you are NOT running as root for this script (except hardening.sh)."

check_deps
setup_env
create_workspaces
start_stack
pull_models
print_status
