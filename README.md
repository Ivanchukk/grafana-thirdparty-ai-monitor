# Grafana AI Operations Assistant

A local, working Grafana App Plugin for evidence-based troubleshooting. React/TypeScript runs inside Grafana; a FastAPI service uses **Microsoft Agent Framework** and `OpenAIChatCompletionClient` to execute seven read-only tools. The default mock model still uses the real framework function-calling loop, real Grafana queries and real Python calculations.

## Start

Prerequisites: Docker Desktop with Linux containers, Docker Compose **2.24.4+** (for `!override`), and sufficient memory for the initial plugin build (8 GB recommended). Docker downloads public images and packages during the first build. At runtime, the application uses local services and your configured internal AI endpoint. Native Node/Python installations are unnecessary for startup.

```sh
docker compose up --build -d
docker compose wait bootstrap
```

Or run `./scripts/start.ps1` in PowerShell or `sh scripts/start.sh` on Linux/macOS. These also show your generated local login password. The initial npm/Grafana downloads may take several minutes.

| Component | Local address |
| --- | --- |
| Grafana assistant | http://localhost:3000/a/local-aiops-app/investigate |
| Demo dashboard | http://localhost:3000/d/elasticsearch-demo |
| Prometheus | http://localhost:9090 |
| FastAPI health / API documentation | http://localhost:8008/health / http://localhost:8008/docs |
| Simulated exporter | http://localhost:9101/metrics |

All published ports bind to `127.0.0.1`. Grafana requires login. Username: **admin**. Retrieve the random password from the local Docker volume:

```sh
docker compose exec -T backend python -c "from pathlib import Path; print(Path('/run/ai-secrets/admin_password').read_text())"
```

No API keys, password files, service-account tokens or browser authentication state belong in Git. `.env` and Playwright authentication files are ignored. Credentials are generated in a named Docker volume; Grafana stores the proxy secret in `secureJsonData`.

Startup automatically builds and installs the unsigned development plugin, provisions Prometheus and the ten-panel dashboard, creates a **Viewer** service account, and configures the authenticated plugin proxy. There is no manual dashboard/plugin installation. After startup, allow approximately 20 seconds of scrapes for counter-rate panels. The dashboard lives in **AI Operations Demo**; the app is **AI Operations Assistant → Investigate** in Grafana navigation. Each dashboard panel menu offers **Extensions → Analyze with AI**. The demo dashboard has an AI link at the top.

## Architecture

```text
Browser / Grafana React app
  → authenticated Grafana plugin proxy (server injects secret)
  → FastAPI → one Microsoft Agent Framework troubleshooting agent
                ├─ get_dashboard_context
                ├─ query_panel_data → Grafana POST /api/ds/query → Prometheus
                ├─ analyze_statistics / detect_anomalies / analyze_trends
                ├─ correlate_metrics
                └─ search_documentation → local Elasticsearch knowledge
  → internal OpenAI-compatible Chat Completions model (or local mock transport)

Three simulated Elasticsearch nodes → exporter /metrics → Prometheus
```

`compose.yaml` extends the official `@grafana/create-plugin@7.15.1` App Plugin Docker development configuration under `local-aiops-app/.config/`. That generated folder is unchanged. The extension disables anonymous admin access and adds health checks, local port bindings, a plugin build volume and the other services. The plugin is built with the generated webpack configuration. Grafana and its libraries are pinned to **13.2.4**.

The Python service queries Grafana with a dedicated Viewer token. Only Grafana reads and `POST /api/ds/query` are allowed by the adapter. The agent has no filesystem, shell, deployment or infrastructure-changing tool. The simulator's control endpoint changes **demo data only**, and is separate from the agent tools.

## Use and simulate incidents

Choose the dashboard, time range, Cluster and Node filters. Multi-select variables support All or individual nodes. Analyze Dashboard starts an investigation; the chat composer accepts follow-ups. Each answer includes observations, possible explanations, investigations to perform next and documentation references. Expand **Investigation trace** to inspect tool arguments, queried expressions, summary values and results.

Example questions:

- Is there anything wrong with my Elasticsearch cluster?
- Why is search latency increasing?
- Is JVM heap pressure isolated to one node?
- Which panels support that finding, and what should I check next?

```sh
curl -X POST http://localhost:9101/scenario/normal
curl -X POST http://localhost:9101/scenario/jvm_pressure
curl -X POST http://localhost:9101/scenario/search_degradation
```

PowerShell: `./scripts/scenario.ps1 jvm_pressure`. Current state: http://localhost:9101/scenario.

Incidents ramp over **40 seconds** on `es-node-2`. JVM pressure raises heap, GC time and latency. Search degradation increases demand, latency and rejection rates. Other nodes stay near baseline. Prometheus scrapes every two seconds; use the last five minutes and allow approximately one minute for clear rate/quantile changes. Returning to normal retains historical incident samples in the selected window; narrow the range to assess recovery.

The exporter emits real cumulative counters and classic histogram buckets. Panel PromQL applies `rate` and `histogram_quantile`. Test fixtures are generated deterministically by `demo/simulation.py`, as described in `tests/fixtures/scenarios.json`, providing 30 minutes of history instantly without waiting for historical scrapes. Fixture data is never substituted into the running app's Grafana queries.

## Connect your internal AI

Copy `.env.example` to `.env`, then set:

```dotenv
MOCK_AI=false
AI_BASE_URL=http://host.docker.internal:8001/v1
AI_API_KEY=your-internal-key
AI_MODEL=your-model-name
```

Use your actual endpoint and credentials. `AI_BASE_URL` includes `/v1` where your server requires it. `host.docker.internal` reaches a server on the host; a DNS/IP address can reach your on-premise model. The endpoint must support the OpenAI **Chat Completions** wire format and function/tool calling, including multiple tool-result round trips. No Azure account is required. Missing live configuration fails explicitly; it does not silently fall back to mock.

```sh
docker compose up -d --force-recreate backend
```

Reload the assistant and confirm the **INTERNAL AI · LIVE** label. API keys remain in the Python service. For self-signed internal TLS, install your organization's CA into the backend container rather than disabling verification.

Mock mode is visibly labelled **MOCK AI · DEVELOPMENT**. It implements the OpenAI tool-call protocol using an in-process HTTP mock transport, then lets Agent Framework execute tools and return their results. It does not test a real model's reasoning or network connectivity.

## Tests

Run the complete deterministic unit + infrastructure + live metric integration suite after startup:

```sh
docker compose --profile test run --no-deps --build --rm tests
```

This tests all services, plugin registration, authenticated proxy behavior, service-account write denial, dashboard variables, all ten panel queries, numerical calculations, reset-aware counters, aligned correlation, normal/JVM/search fixtures, seven actual framework function calls, a live JVM incident through exporter → Prometheus → Grafana → agent, exact agreement between findings and queried values, and follow-up chat. The live incident test takes about one minute and restores the normal scenario afterwards.

Unit tests only (no Grafana required after building the image):

```sh
docker compose run --no-deps --rm backend pytest -q tests/test_analysis.py tests/test_agent.py
```

Frontend and browser checks (Node 22+):

```sh
cd local-aiops-app
npm ci
npm run typecheck
npm run build
npx playwright install chromium
```

From the project root, `./scripts/test-browser.ps1` reads the generated local password into the current process and runs `@grafana/plugin-e2e` tests. Browser screenshots and traces are saved under `artifacts/` and `local-aiops-app/test-results/`. On other platforms, set `GRAFANA_ADMIN_PASSWORD` using the password retrieval command, then run `npm run e2e` inside the plugin directory. Authentication state is ignored by Git.

Additional real AI integration test, **only after configuring your endpoint**:

```sh
docker compose --profile test run --no-deps --build --rm -e LIVE_AI_TEST=true tests pytest -q tests/test_integration.py::test_real_internal_ai
```

The real AI test is skipped by default. A successful mock test is not evidence that your internal model works.

## Limits and development

- This is a local proof of concept, not a production multi-tenant deployment. The service account can read the local Grafana organization; it does not impersonate individual folder-level access permissions. Do not attach production data sources without designing that authorization boundary.
- Existing **Prometheus** dashboard definitions are supported, including nested rows, per-target data sources, query descriptions and common variables. Query variables support `label_values`; custom, constant, textbox, interval and Prometheus datasource variables are supported. Other data source types, query-variable expressions and raw variable formatting return explicit errors. Arbitrary plugin transformations, library panels, repeated panels and expression/math targets are not evaluated.
- Dashboard URL time ranges and `var-*` values are preserved by the panel-menu extension. Relative `now-<n>s/m/h/d`, epoch milliseconds and ISO timestamps are accepted. The assistant time controls are independent once opened; maximum query range is **24 hours**.
- Per investigation: at most **30 panels**, **120 series**, **60,000 points**, four concurrent Grafana requests and two concurrent investigations. Queries time out after 20 seconds; agent execution after 115 seconds. The framework allows ten model/tool iterations and 24 tool executions, with a second hard tool budget. Raw arrays remain in Python.
- Numerical analysis handles gauges, reset-aware raw counters, already normalized rates and histogram-derived quantiles. Correlation matches actual timestamps, requires three overlapping samples and returns no coefficient for constant series. Detection uses demo limits and robust deviations; it is not a trained anomaly model. Total heap occupancy is not Elasticsearch's old-generation memory-pressure indicator. Three breached samples do not prove a long-duration production incident.
- Sessions are in memory, isolated by the authenticated Grafana user, expire after 30 minutes and retain up to six recent exchanges. Restarting the backend clears chats. Mock answers follow a fixed investigation plan and are intentionally less adaptive than a real model.
- Initial package/image downloads need network access. No hosted AI, vector database, Kubernetes, real Elasticsearch cluster or automatic infrastructure modification is included.

Source layout: `backend/` API/agent/tools, `demo/` exporter and fixture generator, `local-aiops-app/` official Grafana scaffold/frontend, `knowledge/elasticsearch/` referenced local documentation, `dashboards/` and `provisioning/` Grafana resources, `tests/` backend and integration tests, `scripts/` startup/bootstrap/scenario helpers.

After source changes, rerun `docker compose up --build -d`. Plugin metadata (`plugin.json`) changes require a **Grafana restart**: `docker compose restart grafana`. To follow logs: `docker compose logs -f backend grafana`. Stop without deleting history or credentials with `docker compose down`.

Official implementation references: [Grafana plugin tools](https://grafana.com/developers/plugin-tools), [authenticated app proxy](https://grafana.com/developers/plugin-tools/how-to-guides/app-plugins/add-authentication-for-app-plugins), [UI extension points](https://grafana.com/developers/plugin-tools/reference/ui-extensions-reference/extension-points), [Microsoft function tools](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools), and [OpenAI-compatible provider setup](https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting/openai-endpoints). Elasticsearch references accompany each local knowledge document.

## Local verification — 2026-10-21

- Backend suite: **16 passed, 1 skipped**. Includes a live JVM incident, actual Grafana/Prometheus values, seven framework-executed tools, read-only permissions and follow-up chat.
- Browser suite: **3 passed**, using `@grafana/plugin-e2e` and Chromium. Covers login, app loading, node selection, chat, dashboard charts and **Extensions → Analyze with AI**.
- TypeScript checking, ESLint and the production webpack build passed.
- Grafana, Prometheus, exporter and backend were all healthy and returned HTTP 200 from their health endpoints.
- The real internal AI test was **not run**: no model endpoint or credentials were provided. All model tests used the explicitly labelled mock transport.

Evidence: [assistant screenshot](artifacts/assistant.png), [dashboard screenshot](artifacts/dashboard.png), [backend test report](artifacts/backend-tests.xml), [verification record](artifacts/verification.json). The test harness restores the normal simulator scenario. This computer's Docker VM is limited to 1 GB RAM and two processors; cold builds and browser loads were slow. Short throughput dips around exporter restarts should be checked against scrape continuity before interpreting them as workload changes.
