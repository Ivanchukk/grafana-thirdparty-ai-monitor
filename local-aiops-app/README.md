# AI Operations Assistant — Grafana App Plugin

This directory was generated with the official `@grafana/create-plugin@7.15.1` App template. Its generated webpack and Docker configuration under `.config/` remains unchanged.

Use the **parent directory's README and `docker compose up --build -d`** to run the complete authenticated MVP. The standalone generated `docker-compose.yaml` is only the scaffold base, extended by the root `compose.yaml` with the backend, provisioning, generated credentials and metrics services.

Frontend development: `npm ci`, `npm run typecheck`, `npm run lint`, `npm run build`. Rebuild the root `plugin-build` service after changes, then restart Grafana. `plugin.json` changes always require a Grafana restart.

Browser tests use `@grafana/plugin-e2e`. Run `../scripts/test-browser.ps1` from the project root or set `GRAFANA_ADMIN_PASSWORD` to the generated local credential before `npm run e2e`. See the root README for complete instructions and limitations.
