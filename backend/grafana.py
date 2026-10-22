"""Read-only Grafana adapter. Only stored Prometheus panel expressions can be executed."""
import asyncio
import copy
import json
import math
import os
import re
import time
from pathlib import Path
import httpx
from backend.analysis import metric_type, statistics

MAX_RANGE = 86400
MAX_SERIES = 120
MAX_POINTS = 60000
MAX_RESPONSE_BYTES = 8*1024*1024
QUERY_GATE = asyncio.Semaphore(4)


def time_range(start: str, end: str) -> tuple[int, int]:
    now = int(time.time()*1000)
    def parse(value):
        if value == "now":
            return now
        match = re.fullmatch(r"now-(\d+)([smhd])", value)
        if match:
            return now-int(match[1])*{"s": 1000, "m": 60000, "h": 3600000, "d": 86400000}[match[2]]
        if value.isdigit():
            return int(value)
        from datetime import datetime
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()*1000)
    a, b = parse(start), parse(end)
    if b <= a or b-a > MAX_RANGE*1000:
        raise ValueError("Choose a positive time range of at most 24 hours")
    if b > now+60000:
        raise ValueError("Time range cannot be in the future")
    return a, b


def interpolate(expression, variables, interval=10, duration=1800):
    builtins = {"__interval": f"{interval}s", "__interval_ms": str(interval*1000), "__rate_interval": f"{max(15, interval*4)}s", "__range": f"{duration}s", "__range_s": str(duration), "__range_ms": str(duration*1000)}
    def replace(match):
        name, fmt = (match[1] or match[3]), match[2]
        if name in builtins:
            return builtins[name]
        if name not in variables:
            raise ValueError(f"Unresolved dashboard variable: {name}")
        value = variables[name]
        items = value if isinstance(value, list) else [str(value)]
        if "$__all" in items or "All" in items:
            return ".*"
        if fmt == "raw":
            raise ValueError("Raw variable interpolation is disabled; use regex, csv, or a datasource variable")
        if fmt == "csv":
            return ",".join(str(x).replace('"', '\\"') for x in items)
        if fmt not in (None, "regex"):
            raise ValueError(f"Unsupported variable format: {fmt}")
        # Prometheus regex escaping followed by PromQL string escaping.
        escape_regex = fmt == "regex" or isinstance(value, list)
        return "|".join(re.escape(str(x)) if escape_regex else str(x) for x in items).replace("\\", "\\\\").replace('"', '\\"')
    return re.sub(r"\$\{(\w+)(?::(\w+))?\}|\$(\w+)", replace, expression)


def flatten(panels):
    for panel in panels:
        if panel.get("targets"):
            yield panel
        yield from flatten(panel.get("panels", []))


class Grafana:
    def __init__(self, client=None):
        self.client = client
        self.base = os.getenv("GRAFANA_URL", "http://grafana:3000")

    async def request(self, method, path, **kwargs):
        if method not in ("GET", "POST") or (method == "POST" and path != "/api/ds/query"):
            raise ValueError("Only Grafana read operations are permitted")
        token = Path(os.getenv("GRAFANA_TOKEN_FILE", "/run/ai-secrets/grafana_token")).read_text().strip()
        async with QUERY_GATE:
            async with httpx.AsyncClient(base_url=self.base, timeout=20, headers={"Authorization": f"Bearer {token}"}, follow_redirects=False) as client:
                if self.client:
                    response = await self.client.request(method, path, **kwargs)
                    response.raise_for_status()
                    if len(response.content) > MAX_RESPONSE_BYTES:
                        raise ValueError("Grafana response exceeds 8 MiB; narrow the query")
                    return response.json()
                async with client.stream(method, path, **kwargs) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise ValueError("Grafana response exceeds 8 MiB; narrow the query")
                        chunks.append(chunk)
                    return json.loads(b"".join(chunks))

    async def dashboards(self):
        return await self.request("GET", "/api/search", params={"type": "dash-db", "limit": 100})

    async def context(self, uid, selected=None, start="now-30m", end="now"):
        if not re.fullmatch(r"[\w-]{1,128}", uid):
            raise ValueError("Invalid dashboard UID")
        response = await self.request("GET", f"/api/dashboards/uid/{uid}")
        dashboard = response["dashboard"]
        definitions = dashboard.get("templating", {}).get("list", [])
        selected = selected or {}
        names = {v["name"] for v in definitions}
        if set(selected)-names:
            raise ValueError("Unknown dashboard variable")
        values, variables = {}, []
        datasources = await self.request("GET", "/api/datasources")
        prom = [d for d in datasources if d["type"] == "prometheus"]
        default_ds = next((d for d in prom if d.get("isDefault")), prom[0] if prom else {})
        for v in definitions:
            name = v["name"]
            current = selected.get(name, v.get("current", {}).get("value", "$__all" if v.get("includeAll") else ""))
            options = v.get("options", [])
            query = v.get("query", "")
            if isinstance(query, dict):
                query = query.get("query", "")
            if v["type"] == "query":
                match = re.fullmatch(r"label_values\((?:(.+),\s*)?(\w+)\)", query)
                if not match:
                    raise ValueError(f"Variable {name}: this MVP supports Prometheus label_values queries")
                selector, label = match.groups()
                ds = v.get("datasource") or default_ds
                ds_uid = ds.get("uid", default_ds.get("uid")) if isinstance(ds, dict) else ds
                params = {"match[]": interpolate(selector, values)} if selector else {}
                data = await self.request("GET", f"/api/datasources/proxy/uid/{ds_uid}/api/v1/label/{label}/values", params=params)
                options = [{"text": x, "value": x} for x in data.get("data", [])][:100]
            elif v["type"] == "datasource":
                options = [{"text": d["name"], "value": d["uid"]} for d in prom]
            elif v["type"] == "custom":
                options = [{"text": x.strip(), "value": x.strip()} for x in query.split(",")]
            elif v["type"] not in ("constant", "textbox", "interval"):
                raise ValueError(f"Unsupported variable type: {v['type']}")
            allowed = [o["value"] for o in options]
            if v.get("includeAll"):
                options = [{"text": "All", "value": "$__all"}, *[o for o in options if o["value"] != "$__all"]]
                allowed.append("$__all")
            items = current if isinstance(current, list) else [current]
            if name in selected and allowed and any(x not in allowed for x in items):
                raise ValueError(f"Invalid selection for {name}")
            if name not in selected and allowed and any(x not in allowed for x in items):
                current = "$__all" if v.get("includeAll") else allowed[0]
            values[name] = current
            variables.append({"name": name, "label": v.get("label") or name, "type": v["type"], "multi": v.get("multi", False), "value": current, "options": options})
        a, b = time_range(start, end)
        panels = [{"id": p["id"], "title": p.get("title", "Untitled"), "description": p.get("description", ""),
                   "datasource": p.get("datasource") or default_ds,
                   "unit": p.get("fieldConfig", {}).get("defaults", {}).get("unit", "short"),
                   "targets": [t for t in p.get("targets", []) if not t.get("hide")]} for p in flatten(dashboard.get("panels", []))]
        return {"uid": uid, "title": dashboard["title"], "panels": panels, "variables": variables, "selected_variables": values,
                "time_range": {"from": start, "to": end, "from_ms": a, "to_ms": b}, "datasources": [{"uid": d["uid"], "type": d["type"], "name": d["name"]} for d in datasources]}

    async def panel_data(self, context, panel_ids=None):
        panels = [p for p in context["panels"] if not panel_ids or p["id"] in panel_ids]
        if len(panels) > 30:
            raise ValueError("At most 30 panels per investigation")
        start, end = context["time_range"]["from_ms"], context["time_range"]["to_ms"]
        interval = max(2, math.ceil((end-start)/1000/300))
        series, errors = [], []
        async def query(p):
            queries, expressions = [], {}
            if len(p["targets"]) > 20:
                raise ValueError("At most 20 query targets per panel")
            for i, original in enumerate(p["targets"]):
                t = copy.deepcopy(original)
                if not t.get("expr"):
                    raise ValueError("Only Prometheus expression targets are supported")
                ds = t.get("datasource") or p["datasource"]
                if isinstance(ds, str):
                    ds = next((d for d in context["datasources"] if d["uid"] == ds or d["name"] == ds), {"uid": ds, "type": "prometheus"})
                ds = {"uid": ds["uid"], "type": ds.get("type", "prometheus")}
                if ds["uid"].startswith("$"):
                    name = ds["uid"].strip("${}")
                    ds["uid"] = context["selected_variables"][name]
                if ds["type"] != "prometheus":
                    raise ValueError("Only Prometheus data sources are supported in this MVP")
                expr = interpolate(t["expr"], context["selected_variables"], interval, (end-start)//1000)
                # Normalize plain counter selectors before numerical analysis; do not derive rates twice.
                if re.fullmatch(r"[\w:]+_total(?:\{.*\})?", expr):
                    expr = f"rate({expr}[{max(15, interval*4)}s])"
                if "_bucket" in expr and "histogram_quantile" not in expr:
                    raise ValueError("Use histogram_quantile for classic histogram bucket panels")
                ref = t.get("refId", chr(65+i))
                expressions[ref] = expr
                queries.append({**t, "refId": ref, "expr": expr, "datasource": ds, "instant": False, "range": True, "format": "time_series", "maxDataPoints": 301, "intervalMs": interval*1000})
            response = await self.request("POST", "/api/ds/query", json={"from": str(start), "to": str(end), "queries": queries})
            found = []
            for ref, result in response.get("results", {}).items():
                if result.get("error"):
                    raise ValueError(result["error"])
                for frame in result.get("frames", []):
                    fields = frame["schema"]["fields"]
                    data = frame["data"]["values"]
                    ti = next((j for j, f in enumerate(fields) if f["type"] == "time"), None)
                    if ti is None:
                        continue
                    for j, field in enumerate(fields):
                        if field["type"] != "number":
                            continue
                        labels = field.get("labels", {})
                        expr = expressions[ref]
                        points = [[t/1000, v] for t, v in zip(data[ti], data[j]) if t is not None and v is not None and math.isfinite(v)]
                        found.append({"id": f"{p['id']}:{ref}:{len(found)}", "panel_id": p["id"], "panel_title": p["title"], "metric": metric_type(expr),
                                      "labels": labels, "points": points, "expression": expr, "unit": p["unit"], "kind": "histogram_quantile" if "histogram_quantile" in expr else "rate" if re.search(r"\b(?:rate|irate|increase)\(", expr) else "gauge"})
            return found
        results = await asyncio.gather(*(query(p) for p in panels), return_exceptions=True)
        for p, result in zip(panels, results):
            if isinstance(result, Exception):
                errors.append({"panel_id": p["id"], "panel_title": p["title"], "error": str(result)[:400]})
            else:
                series.extend(result)
        if len(series) > MAX_SERIES or sum(len(s["points"]) for s in series) > MAX_POINTS:
            raise ValueError("Query result exceeds investigation limits; narrow the variables or time range")
        return series, errors
