#!/usr/bin/env sh
set -eu
docker compose up --build -d
docker compose wait bootstrap
printf 'Grafana: http://localhost:3000/a/local-aiops-app/investigate\nUsername: admin. Local password:\n'
docker compose exec -T backend python -c "from pathlib import Path; print(Path('/run/ai-secrets/admin_password').read_text())"
