#!/usr/bin/env bash
# =============================================================================
# Full cleanup of Docker environment before fresh install
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${RED}[WARNING]${NC} This will remove ALL Docker containers, images, volumes, and networks."
echo -e "${YELLOW}[!]${NC} Ollama models will also be deleted (~20-80GB freed)."
echo ""
read -r -p "Type YES to confirm full cleanup: " confirm
[[ "$confirm" != "YES" ]] && { echo "Aborted."; exit 0; }

echo "[*] Stopping all containers..."
docker stop "$(docker ps -aq)" 2>/dev/null || true

echo "[*] Removing all containers, images, volumes, networks..."
docker system prune -a -f --volumes

echo "[*] Removing Ollama model data..."
read -r -p "Also remove ~/.ollama model cache? [y/N]: " yn
if [[ "${yn,,}" == "y" ]]; then
  OLLAMA_DIR="${HOME}/.ollama"
  if [[ -d "$OLLAMA_DIR" ]]; then
    mv "$OLLAMA_DIR" "${OLLAMA_DIR}.bak.$(date +%Y%m%d_%H%M%S)" || sudo rm -rf "$OLLAMA_DIR"
    echo "[+] Moved $OLLAMA_DIR to backup."
  fi
fi

echo "[*] Restarting Docker daemon..."
sudo systemctl restart docker

echo "[*] Verify clean state:"
docker run --rm hello-world

echo "[+] Cleanup complete. Ready for fresh install."
