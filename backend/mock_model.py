"""Deterministic OpenAI wire-protocol mock. It requests tools; Agent Framework executes them."""
import json
import time
import httpx


def display(value, unit):
    if unit == "percentunit":
        return f"{value*100:.2f}%"
    if unit == "s":
        return f"{value:.4f} seconds"
    return f"{value:.4f} {unit or ''}".strip()


class MockModel:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        messages = body["messages"]
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        results = {}
        call_names = {}
        for m in messages[last_user+1:]:
            for call in m.get("tool_calls", []):
                call_names[call["id"]] = call["function"]["name"]
            if m["role"] == "tool":
                try:
                    results[call_names[m["tool_call_id"]]] = json.loads(m["content"])
                except (KeyError, ValueError):
                    pass
        plan = [("get_dashboard_context", {}), ("query_panel_data", {"panel_ids": []}),
                ("analyze_statistics", {}), ("detect_anomalies", {}), ("analyze_trends", {}),
                ("correlate_metrics", {}), ("search_documentation", {"query": "JVM heap garbage collection CPU search latency thread pool rejections"})]
        pending = next(((name, args) for name, args in plan if name not in results), None)
        if pending and body.get("tool_choice") != "none":
            name, args = pending
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{len(results)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
            reason = "tool_calls"
        else:
            findings = results.get("detect_anomalies", {}).get("findings", [])
            summaries = results.get("analyze_statistics", {}).get("statistics", [])
            errors = results.get("query_panel_data", {}).get("errors", [])
            text = ["MOCK AI — deterministic development response.", "Confirmed observations:"]
            if findings:
                for f in findings:
                    state = "active at end of window" if f.get("active_at_end") else "historical breach; recovered at end of window"
                    text.append(f"• {f['title']} on {f['node']}: {f.get('evidence_label', 'peak')} {display(f.get('evidence_value', f['peak']), f.get('unit'))}; latest {display(f['latest'], f.get('unit'))} ({state}). Evidence: {f.get('panel_title') or f['metric']} (panel {f.get('panel_id')}).")
            elif summaries and all(s["count"] >= 3 for s in summaries):
                text.append("No sustained demo operating-limit violations or unusual deviations were detected in the sampled window.")
            else:
                text.append("Insufficient data to assess this time range. Allow more scrapes or broaden the selected window.")
            if errors:
                text.append("Some panel queries failed; the investigation is incomplete.")
            metrics = {f["metric"] for f in findings}
            text.append("\nPossible explanations:")
            if "heap" in metrics and "gc" in metrics:
                text.append("Memory pressure may be contributing to GC activity and search latency. The metrics show temporal association, not confirmed causation.")
            elif "rejections" in metrics and "latency" in metrics:
                text.append("Search workload may be exceeding available processing capacity. Check request volume, expensive queries and resource contention; correlation alone does not establish causation.")
            else:
                text.append("These samples do not establish a root cause.")
            if any(f["title"] == "Unusual drop" and f["metric"] in ("search", "indexing") for f in findings):
                text.append("Short throughput dips may reflect counter restarts or scrape gaps. Check exporter continuity before interpreting them as workload changes.")
            text.extend(["\nRecommended investigations:", "Review the affected time window and compare peer nodes. Inspect GC logs, slow search logs, thread pool queues and shard workload before choosing a change.", "\nSources:"])
            for d in results.get("search_documentation", {}).get("documents", []):
                text.append(f"• {d['title']}: {d['source']}")
            message, reason = {"role": "assistant", "content": "\n".join(text)}, "stop"
        return httpx.Response(200, json={"id": "mock-chat", "object": "chat.completion", "created": int(time.time()), "model": "deterministic-mock", "choices": [{"index": 0, "message": message, "finish_reason": reason}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
