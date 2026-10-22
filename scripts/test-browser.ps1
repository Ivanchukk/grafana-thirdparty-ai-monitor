$ErrorActionPreference = 'Stop'
$env:GRAFANA_ADMIN_PASSWORD = (docker compose exec -T backend python -c "from pathlib import Path; print(Path('/run/ai-secrets/admin_password').read_text())").Trim()
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Push-Location (Join-Path $PSScriptRoot '../local-aiops-app')
try {
    npm run e2e
    $testExit = $LASTEXITCODE
} finally {
    Pop-Location
    Remove-Item Env:GRAFANA_ADMIN_PASSWORD
}
exit $testExit
