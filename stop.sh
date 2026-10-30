#!/usr/bin/env bash
# Stops the stack and the tunnel. Products and images are kept.
set -euo pipefail
cd "$(dirname "$0")"

docker compose down

if [ -f .tunnel.pid ]; then
  kill "$(cat .tunnel.pid)" 2>/dev/null || true
  rm -f .tunnel.pid
fi

echo "Остановлено. Данные сохранены."
