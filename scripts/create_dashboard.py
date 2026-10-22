"""Regenerate the versioned dashboard using only documented dashboard JSON fields."""
import json
from pathlib import Path

selector = '{cluster=~"${cluster:regex}",node=~"${node:regex}"}'
specs = [
    ("CPU usage", "CPU utilization by Elasticsearch node. Compare with request volume and GC activity.", "percentunit", f"es_cpu_usage_ratio{selector}"),
    ("JVM heap usage", "Total JVM heap occupancy, not old-generation pressure. Demo warning above 85%.", "percentunit", f"es_jvm_heap_usage_ratio{selector}"),
    ("Garbage collection activity", "Fraction of wall time spent in GC, computed from a cumulative seconds counter.", "percentunit", f"rate(es_jvm_gc_seconds_total{selector}[$__rate_interval])"),
    ("Search latency · p95", "Estimated 95th percentile request duration from classic histogram buckets.", "s", f"histogram_quantile(0.95, sum by (le, cluster, node) (rate(es_search_duration_seconds_bucket{selector}[$__rate_interval])))"),
    ("Search throughput", "Search requests per second. The cumulative counter is converted to a rate.", "reqps", f"rate(es_search_requests_total{selector}[$__rate_interval])"),
    ("Indexing throughput", "Indexed documents per second, calculated from a cumulative counter.", "ops", f"rate(es_indexing_documents_total{selector}[$__rate_interval])"),
    ("Thread pool rejections", "Rejected search tasks per second. Sustained rejections warrant workload investigation.", "ops", f"rate(es_search_thread_pool_rejections_total{selector}[$__rate_interval])"),
    ("Memory usage", "Simulated node resident memory consumption, including non-heap use.", "bytes", f"es_memory_used_bytes{selector}"),
    ("Active connections", "Open client connections per node, related to simulated search demand.", "short", f"es_active_connections{selector}"),
    ("Node availability", "One means the node is available; zero indicates unavailability.", "short", f"es_node_up{selector}"),
]
ds = {"type": "prometheus", "uid": "demo-prometheus"}
dashboard = {"uid": "elasticsearch-demo", "title": "Elasticsearch · Infrastructure Overview", "description": "Three simulated nodes with real Prometheus time series. Activate incidents from the local exporter API.", "schemaVersion": 41, "version": 1, "tags": ["aiops", "demo", "elasticsearch"], "timezone": "browser", "refresh": "5s", "time": {"from": "now-30m", "to": "now"}, "editable": False,
 "links": [{"title": "Analyze with AI", "url": "/a/local-aiops-app/investigate?dashboard=elasticsearch-demo", "includeVars": True, "keepTime": True, "type": "link"}],
 "templating": {"list": [
    {"name": "cluster", "label": "Cluster", "type": "query", "datasource": ds, "query": "label_values(es_node_up, cluster)", "refresh": 1, "multi": True, "includeAll": True, "current": {"text": "All", "value": "$__all"}, "options": []},
    {"name": "node", "label": "Node", "type": "query", "datasource": ds, "query": 'label_values(es_node_up{cluster=~"${cluster:regex}"}, node)', "refresh": 1, "multi": True, "includeAll": True, "current": {"text": "All", "value": "$__all"}, "options": []}
 ]}, "panels": []}
for i, (title, description, unit, expr) in enumerate(specs):
    dashboard["panels"].append({"id": i+1, "type": "timeseries", "title": title, "description": description, "datasource": ds,
        "gridPos": {"x": (i%2)*12, "y": (i//2)*8, "w": 12, "h": 8}, "targets": [{"refId": "A", "expr": expr, "legendFormat": "{{node}}", "datasource": ds, "range": True}],
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"}, "custom": {"lineWidth": 2, "fillOpacity": 8, "spanNulls": False}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}}})
path = Path(__file__).resolve().parents[1]/"dashboards"/"elasticsearch.json"
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(dashboard, indent=2)+"\n", encoding="utf-8")
print(f"Generated {len(specs)} panels.")
