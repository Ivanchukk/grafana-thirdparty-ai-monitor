"""Runs inside Compose. Real Grafana and Prometheus queries; mocked model, real tools."""
import asyncio
import os
import time
from pathlib import Path
import httpx
import pytest
from backend.grafana import Grafana
from backend.agent import investigate

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "true", reason="Requires Docker Compose services")


def admin_client():
    return httpx.Client(base_url="http://grafana:3000", auth=("admin", Path("/run/ai-secrets/admin_password").read_text().strip()), timeout=125)


def test_infrastructure_and_authentication():
    for url in ("http://grafana:3000/api/health", "http://prometheus:9090/-/ready", "http://exporter:9101/health", "http://backend:8000/health"):
        assert httpx.get(url).is_success
    assert 'es_jvm_heap_usage_ratio{' in httpx.get("http://exporter:9101/metrics").text
    assert httpx.get("http://backend:8000/dashboards").status_code == 401
    assert httpx.get("http://grafana:3000/api/plugin-proxy/local-aiops-app/backend/dashboards").status_code in (401, 302)
    with admin_client() as client:
        settings = client.get("/api/plugins/local-aiops-app/settings").json()
        assert settings["enabled"]
        assert settings["secureJsonFields"]["backendKey"]
        assert "backendKey" not in settings.get("jsonData", {})
        result = client.get("/api/plugin-proxy/local-aiops-app/backend/dashboards")
        assert result.status_code == 200, result.text
        assert any(d["uid"] == "elasticsearch-demo" for d in result.json())
        accounts = client.get("/api/serviceaccounts/search", params={"query": "aiops-readonly"}).json()["serviceAccounts"]
        assert next(a for a in accounts if a["name"] == "aiops-readonly")["role"] == "Viewer"
    token = Path("/run/ai-secrets/grafana_token").read_text().strip()
    denied = httpx.post("http://grafana:3000/api/dashboards/db", headers={"Authorization": f"Bearer {token}"}, json={"dashboard": {"title": "must-not-create"}})
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_queries_and_variables():
    grafana = Grafana()
    ctx = await grafana.context("elasticsearch-demo")
    assert len(ctx["panels"]) == 10
    assert len(next(v for v in ctx["variables"] if v["name"] == "node")["options"]) == 4
    series, errors = await grafana.panel_data(ctx)
    assert errors == [], errors
    assert len(series) == 30
    assert all(s["points"] for s in series)
    selected = await grafana.context("elasticsearch-demo", {"cluster": ["demo-es"], "node": ["es-node-2"]})
    filtered, errors = await grafana.panel_data(selected)
    assert not errors
    assert {s["labels"]["node"] for s in filtered} == {"es-node-2"}
    assert len(filtered) == 10


@pytest.mark.asyncio
async def test_live_jvm_incident_evidence_and_followup():
    try:
        start_ms = int(time.time()*1000)
        assert httpx.post("http://exporter:9101/scenario/jvm_pressure").is_success
        # Poll actual Prometheus observations, not a fabricated fixture or elapsed-hour wait.
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            sample = httpx.get("http://prometheus:9090/api/v1/query", params={"query": 'es_jvm_heap_usage_ratio{node="es-node-2"}'}).json()["data"]["result"]
            if sample and float(sample[0]["value"][1]) > .9:
                await asyncio.sleep(8)
                break
            await asyncio.sleep(2)
        with admin_client() as client:
            body = {"dashboard_uid": "elasticsearch-demo", "from_time": str(start_ms), "question": "Is there anything wrong with my Elasticsearch cluster?"}
            response = client.post("/api/plugin-proxy/local-aiops-app/backend/chat", json=body)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["mode"] == "mock"
            assert result["status"] == "warning"
            findings = result["findings"]
            assert {"heap", "gc", "latency"} <= {f["metric"] for f in findings}
            assert all(f["node"] == "es-node-2" for f in findings)
            assert result["tool_calls"] == 7
            assert all("error" not in t["result"] for t in result["trace"])
            stats = {s["id"]: s for s in result["statistics"]}
            for f in findings:
                assert f["peak"] == stats[f["series_id"]]["max"]
                assert f["latest"] == stats[f["series_id"]]["last"]
            assert "es-node-2" in result["answer"]
            body.update(session_id=result["session_id"], question="Which node is affected and what should I check next?")
            followup = client.post("/api/plugin-proxy/local-aiops-app/backend/chat", json=body).json()
            assert followup["session_id"] == result["session_id"]
            assert followup["turn"] == 2
            assert "es-node-2" in followup["answer"]
    finally:
        httpx.post("http://exporter:9101/scenario/normal")


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("LIVE_AI_TEST") != "true", reason="Set LIVE_AI_TEST=true and configure a real internal model")
async def test_real_internal_ai():
    grafana = Grafana()
    ctx = await grafana.context("elasticsearch-demo")
    result = await investigate(grafana, ctx, "Analyze the selected dashboard. Use tools for your evidence.", mock=False)
    tools = {t["tool"] for t in result["trace"] if "error" not in t["result"]}
    assert "query_panel_data" in tools
    assert len(tools) >= 3
    assert result["statistics"]
    assert result["mode"] == "live"
    assert result["answer"]
