$ErrorActionPreference = 'Stop'
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose wait bootstrap
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Grafana: http://localhost:3000/a/local-aiops-app/investigate'
Write-Host 'Username: admin. Local password:'
docker compose exec -T backend python -c "from pathlib import Path; print(Path('/run/ai-secrets/admin_password').read_text())"
