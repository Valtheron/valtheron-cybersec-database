#!/usr/bin/env bash
# ============================================================
# Valtheron CyberSec – Full Cleanup Script
# Removes all containers, images, volumes, and networks.
# OPTIONAL: backs up Ollama models before purge.
# ============================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }

warn "This will destroy ALL Docker containers, images, and volumes!"
read -rp "Type 'CLEANUP' to confirm: " CONFIRM
[[ "$CONFIRM" != "CLEANUP" ]] && echo "Aborted." && exit 0

# Optional model backup
read -rp "Backup Ollama models first? [y/N]: " BACKUP
if [[ "${BACKUP,,}" == "y" ]]; then
  BACKUP_DIR="$HOME/ollama-backup-$(date +%Y%m%d_%H%M%S)"
  info "Backing up models to $BACKUP_DIR..."
  cp -r ~/.ollama "$BACKUP_DIR" 2>/dev/null || true
  info "Backup saved to $BACKUP_DIR"
fi

info "Stopping all containers..."
docker stop $(docker ps -aq) 2>/dev/null || true

info "Removing all containers, images, volumes, and networks..."
docker system prune -a -f --volumes

info "Removing Ollama host data..."
sudo rm -rf ~/.ollama /var/lib/docker/volumes/*ollama* 2>/dev/null || true

info "Restarting Docker daemon..."
sudo systemctl restart docker

info "Verifying clean state..."
docker run --rm hello-world >/dev/null 2>&1 && info "Docker daemon healthy" || true

info "Cleanup complete. Run ./scripts/setup.sh to reinstall."
