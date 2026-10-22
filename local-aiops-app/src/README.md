# AI Operations Assistant

Investigate Grafana dashboards using live Prometheus queries, statistical tools and local Elasticsearch documentation. The assistant is read-only and runs through an authenticated Grafana plugin proxy.

Choose a dashboard, time range and variables, then select **Analyze Dashboard** or ask a question. Findings include measured evidence, panel references and an expandable tool trace. Follow-up questions keep the same chat context.

The MVP runs locally with Docker. **MOCK AI** is a deterministic development model that calls real tools through Microsoft Agent Framework. Configure `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` and `MOCK_AI=false` on the Python service to use an internal OpenAI-compatible function-calling model.

See the project root README for startup, generated login credentials, incident controls, tests and supported dashboard features. No credentials are stored in this plugin's browser code.
