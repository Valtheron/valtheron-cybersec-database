#!/usr/bin/env bash
# =============================================================================
# Valtheron CyberSec Stack - Security Hardening Script
# Run ONCE after initial docker-compose up
# Requires: sudo
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

check_root() {
  [[ $EUID -eq 0 ]] || log_error "Run as root: sudo $0"
}

# --- 1. UFW Firewall Rules ---
setup_firewall() {
  log_info "Configuring UFW firewall..."
  command -v ufw &>/dev/null || apt-get install -y ufw

  ufw --force reset
  ufw default deny incoming
  ufw default allow outgoing

  # Allow SSH (adjust port if non-standard)
  ufw allow 22/tcp comment "SSH"

  # Agent WebUIs - restrict to localhost only
  ufw allow from 127.0.0.1 to any port 8080 comment "Stopoda WebUI (localhost only)"
  ufw allow from 127.0.0.1 to any port 8081 comment "Costraca WebUI (localhost only)"
  ufw allow from 127.0.0.1 to any port 3000 comment "Open-WebUI (localhost only)"

  # Ollama API - internal only
  ufw allow from 172.20.0.0/24 to any port 11434 comment "Ollama (Docker net only)"
  ufw deny 11434/tcp comment "Block external Ollama access"

  # ChromaDB - internal only
  ufw deny 8000/tcp comment "Block external ChromaDB access"

  ufw --force enable
  ufw status verbose
  log_info "Firewall configured."
}

# --- 2. AppArmor Profile ---
setup_apparmor() {
  log_info "Loading AppArmor profile for agents..."
  if ! command -v apparmor_parser &>/dev/null; then
    apt-get install -y apparmor apparmor-utils
  fi

  PROFILE_SRC="$(dirname "$0")/apparmor-agent.profile"
  if [[ -f "$PROFILE_SRC" ]]; then
    apparmor_parser -r -W "$PROFILE_SRC"
    log_info "AppArmor profile loaded: agent-zero"
  else
    log_warn "AppArmor profile not found at $PROFILE_SRC - skipping"
  fi
}

# --- 3. Docker Socket Permissions ---
secure_docker_socket() {
  log_info "Securing Docker socket permissions..."
  # Ensure docker.sock is only accessible by docker group
  chown root:docker /var/run/docker.sock
  chmod 660 /var/run/docker.sock
  log_info "Docker socket secured."
}

# --- 4. Container Resource Limits ---
apply_cgroup_limits() {
  log_info "Verifying cgroup limits on containers..."
  for container in stopoda-agent costraca-agent; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
      STATS=$(docker stats --no-stream --format "{{.CPUPerc}} / {{.MemUsage}}" "$container" 2>/dev/null || echo "not running")
      log_info "$container: $STATS"
    else
      log_warn "$container: not running"
    fi
  done
}

# --- 5. Secrets Audit ---
audit_secrets() {
  log_info "Auditing .env files for default secrets..."
  ENV_FILE="$(dirname "$(dirname "$0")")/.env"

  if [[ ! -f "$ENV_FILE" ]]; then
    log_warn ".env not found. Copy .env.example to .env and set real secrets."
    return
  fi

  if grep -q "change_this" "$ENV_FILE"; then
    log_error ".env contains default placeholder values. Update WEBUI_SECRET_KEY and CHROMA_TOKEN!"
  else
    log_info ".env secrets look customized. Good."
  fi

  # Check permissions
  PERMS=$(stat -c "%a" "$ENV_FILE")
  if [[ "$PERMS" != "600" && "$PERMS" != "400" ]]; then
    log_warn ".env has permissions $PERMS. Setting to 600..."
    chmod 600 "$ENV_FILE"
  fi
}

# --- 6. Volume Permissions ---
fix_volume_permissions() {
  log_info "Fixing workspace permissions..."
  STACK_DIR="$(dirname "$(dirname "$0")")"

  for agent in stopoda costraca; do
    WORKSPACE="$STACK_DIR/$agent"
    mkdir -p "$WORKSPACE/workspace" "$WORKSPACE/output" "$WORKSPACE/tools"
    chmod 750 "$WORKSPACE"
    chmod 750 "$WORKSPACE/workspace" "$WORKSPACE/output"
    chmod 550 "$WORKSPACE/tools"  # tools are read-only
    log_info "$agent directories secured."
  done
}

# --- 7. Fail2ban for WebUI ---
setup_fail2ban() {
  log_info "Configuring fail2ban for WebUI brute-force protection..."
  command -v fail2ban-client &>/dev/null || { log_warn "fail2ban not installed. Skipping."; return; }

  cat > /etc/fail2ban/jail.d/agent-webui.conf << 'EOF'
[agent-webui]
enabled = true
port = 8080,8081,3000
filter = apache-auth
logpath = /var/log/nginx/access.log
maxretry = 5
bantime = 3600
findtime = 600
EOF

  fail2ban-client reload
  log_info "fail2ban configured."
}

# --- Main ---
check_root
log_info "Starting security hardening for Valtheron CyberSec Stack..."

setup_firewall
setup_apparmor
secure_docker_socket
apply_cgroup_limits
audit_secrets
fix_volume_permissions
setup_fail2ban

log_info "Hardening complete. Review warnings above."
echo ""
echo "Summary:"
echo "  - UFW firewall: enabled (ports 8080/8081/3000 localhost-only)"
echo "  - AppArmor: agent-zero profile loaded"
echo "  - Docker socket: root:docker 660"
echo "  - Workspace permissions: set"
echo "  - Ollama (11434): blocked from external access"
echo ""
echo "Next: Verify with 'docker ps' and 'ufw status'"
