import pytest
from backend.agent import investigate
from backend.knowledge import KnowledgeBase
from demo.simulation import fixture


class FixtureGrafana:
    def __init__(self, scenario):
        self.scenario = scenario
        self.calls = 0

    async def panel_data(self, context, panel_ids):
        self.calls += 1
        return fixture(self.scenario), []


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,status", [("normal", "healthy"), ("jvm_pressure", "warning"), ("search_degradation", "warning")])
async def test_actual_framework_function_calling(scenario, status):
    grafana = FixtureGrafana(scenario)
    ctx = {"uid": "fixture", "panels": [], "time_range": {}, "selected_variables": {}}
    result = await investigate(grafana, ctx, "Analyze the cluster", mock=True)
    assert grafana.calls == 1
    assert result["status"] == status
    assert result["tool_calls"] == 7
    assert {t["tool"] for t in result["trace"]} == {"get_dashboard_context", "query_panel_data", "analyze_statistics", "detect_anomalies", "analyze_trends", "correlate_metrics", "search_documentation"}
    assert all("error" not in t["result"] for t in result["trace"])
    assert "MOCK AI" in result["answer"]
    assert "causation" in result["answer"] or "root cause" in result["answer"]
    assert result["sources"]
    assert "points" not in str(result["trace"])


def test_documentation_retrieval():
    documents = KnowledgeBase().search("heap garbage collection")
    assert documents[0]["id"] == "jvm-gc"
    assert documents[0]["source"].startswith("https://www.elastic.co/")
