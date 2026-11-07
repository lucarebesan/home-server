#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/pytest -q
rsync -a --delete --exclude .venv --exclude .git --exclude data --exclude .env \
  --exclude __pycache__ --exclude .pytest_cache ./ home@192.168.1.100:ecm-engine/
ssh home@192.168.1.100 'cd ~/ecm-engine && mkdir -p data && docker compose up -d --build && sleep 5 && docker logs --tail 20 ecm-engine'
