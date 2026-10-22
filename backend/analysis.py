"""Bounded numerical operations. Full arrays stay in Python, never in model prompts."""
import math
import re
import numpy as np

# Demo operating limits, not universal Elasticsearch configuration guidance.
LIMITS = {"heap": (.85, "High JVM heap usage"), "cpu": (.85, "High CPU usage"),
          "gc": (.15, "Increased garbage collection"), "latency": (.25, "Elevated search latency"),
          "rejections": (.1, "Search thread pool rejections")}


def clean(points):
    return np.array([[float(t), float(v)] for t, v in points if v is not None and math.isfinite(float(v))], dtype=float).reshape(-1, 2)


def normalize(points, kind="gauge"):
    """Counter derivatives handle resets; rate/histogram-derived series are already normalized."""
    p = clean(points)
    if kind != "counter" or len(p) < 2:
        return p
    dt, dv = np.diff(p[:, 0]), np.diff(p[:, 1])
    dv = np.where(dv < 0, p[1:, 1], dv)
    valid = dt > 0
    return np.column_stack((p[1:, 0][valid], dv[valid]/dt[valid]))


def statistics(series):
    p = normalize(series["points"], series.get("kind", "gauge"))
    base = {k: series.get(k) for k in ("id", "metric", "labels", "panel_id", "panel_title", "unit", "expression", "kind")}
    base["count"] = len(p)
    if not len(p):
        return {**base, "insufficient_data": True}
    v = p[:, 1]
    width = max(1, len(v)//4)
    first, last = float(np.mean(v[:width])), float(np.mean(v[-width:]))
    return {**base, "min": float(v.min()), "max": float(v.max()), "average": float(v.mean()),
            "p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "stddev": float(v.std()),
            "first": float(v[0]), "last": float(v[-1]), "change": float(v[-1]-v[0]),
            "window_change_percent": (last-first)/abs(first)*100 if abs(first) > 1e-12 else None,
            "from": float(p[0, 0]), "to": float(p[-1, 0]),
            "peak_at": float(p[np.argmax(v), 0])}


def anomalies(series):
    p = normalize(series["points"], series.get("kind", "gauge"))
    if len(p) < 3:
        return {"id": series["id"], "issues": [], "insufficient_data": True}
    metric, v = series["metric"], p[:, 1]
    issues = []
    if metric in LIMITS:
        threshold, title = LIMITS[metric]
        if metric in ("cpu", "heap", "gc") and series.get("unit") == "percent":
            threshold *= 100
        if metric == "latency" and series.get("unit") == "ms":
            threshold *= 1000
        bad = v > threshold
    elif metric == "up":
        threshold, title, bad = 1., "Node unavailable", v < 1
    else:
        baseline = v[:max(3, len(v)//2)]
        median = np.median(baseline)
        mad = np.median(np.abs(baseline-median))
        threshold = max(6*1.4826*mad, abs(float(median))*.5, 1e-6)
        bad = np.abs(v-median) > threshold
        title = "Unusual deviation"
    if np.count_nonzero(bad) >= 3:
        evidence_value, evidence_label = float(v.max()), "peak"
        if metric == "up":
            evidence_value, evidence_label = float(v.min()), "minimum"
        elif metric not in LIMITS:
            if np.all(v[bad] < median):
                title = "Unusual drop"
                evidence_value, evidence_label = float(v.min()), "minimum"
            elif np.all(v[bad] > median):
                title = "Unusual spike"
            else:
                evidence_value, evidence_label = float(v[np.argmax(np.abs(v-median))]), "observed"
        issues.append({"title": title, "series_id": series["id"], "node": series["labels"].get("node", "unlabelled"),
                       "metric": metric, "panel_id": series.get("panel_id"), "panel_title": series.get("panel_title"),
                       "peak": float(v.max()), "minimum": float(v.min()), "latest": float(v[-1]), "threshold": threshold,
                       "evidence_value": evidence_value, "evidence_label": evidence_label,
                       "unit": series.get("unit"), "samples_affected": int(np.count_nonzero(bad)), "active_at_end": bool(bad[-1]),
                       "first_observed": float(p[bad][0, 0]), "last_observed": float(p[bad][-1, 0])})
    return {"id": series["id"], "issues": issues, "insufficient_data": False}


def trend(series):
    p = normalize(series["points"], series.get("kind", "gauge"))
    if len(p) < 3:
        return {"id": series["id"], "trend": "insufficient_data"}
    slope = float(np.polyfit(p[:, 0]-p[0, 0], p[:, 1], 1)[0])
    change = slope*(p[-1, 0]-p[0, 0])
    tolerance = max(abs(float(p[:, 1].mean()))*.10, 1e-6)
    return {"id": series["id"], "trend": "stable" if abs(change) < tolerance else "increasing" if slope > 0 else "decreasing", "slope_per_second": slope}


def correlation(left, right):
    a = normalize(left["points"], left.get("kind", "gauge"))
    b = normalize(right["points"], right.get("kind", "gauge"))
    # Grafana range queries use the same step. Match actual timestamps; never correlate index positions.
    av, bv = dict(a.tolist()), dict(b.tolist())
    shared = sorted(av.keys() & bv.keys())
    result = {"left": left["id"], "right": right["id"], "aligned_samples": len(shared), "causation": False}
    if len(shared) < 3:
        return {**result, "pearson": None, "reason": "Insufficient overlapping samples"}
    x, y = [av[t] for t in shared], [bv[t] for t in shared]
    if np.std(x) < 1e-10 or np.std(y) < 1e-10:
        return {**result, "pearson": None, "reason": "Constant series"}
    return {**result, "pearson": float(np.corrcoef(x, y)[0, 1])}


def metric_type(expression):
    mappings = [("heap", "jvm_heap"), ("cpu", "cpu_usage"), ("gc", "jvm_gc"),
                ("latency", "search_duration"), ("rejections", "rejections"),
                ("search", "search_requests"), ("indexing", "indexing_documents"),
                ("memory", "memory_used"), ("connections", "active_connections"), ("up", "node_up")]
    return next((key for key, needle in mappings if needle in expression), "unknown")
