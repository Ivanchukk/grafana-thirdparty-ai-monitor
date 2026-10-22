"""Prometheus exporter with cumulative counters and a classic latency histogram."""
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from demo.simulation import BUCKETS, NODES, SCENARIOS, values
import math

state = {"scenario": "normal", "since": time.monotonic(), "start": time.monotonic()}
counters = {n: {k: 0. for k in ("gc", "search", "indexing", "rejections", "sum", *map(str, BUCKETS))} for n in NODES}


async def tick():
    last = time.monotonic()
    while True:
        now = time.monotonic()
        dt, last = now-last, now
        for n in NODES:
            v = values(n, now-state["start"], state["scenario"], now-state["since"])
            for key in ("gc", "search", "indexing", "rejections"):
                counters[n][key] += dt*v[key]
            counters[n]["sum"] += dt*v["search"]*v["latency"]/math.log(20)
            for b in BUCKETS:
                counters[n][str(b)] += dt*v["search"]*(1-math.exp(-b*math.log(20)/v["latency"]))
        await asyncio.sleep(.5)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(tick())
    yield
    task.cancel()


app = FastAPI(title="Local Elasticsearch simulator", lifespan=lifespan)


@app.get("/health")
@app.get("/scenario")
def status():
    return {"scenario": state["scenario"], "incident_age_seconds": round(time.monotonic()-state["since"], 1), "nodes": NODES}


@app.post("/scenario/{scenario}")
def activate(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"Choose one of {SCENARIOS}")
    state.update(scenario=scenario, since=time.monotonic())
    return status()


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    now = time.monotonic()
    specs = {"cpu": ("es_cpu_usage_ratio", "gauge"), "heap": ("es_jvm_heap_usage_ratio", "gauge"),
             "memory": ("es_memory_used_bytes", "gauge"), "connections": ("es_active_connections", "gauge"),
             "up": ("es_node_up", "gauge"), "gc": ("es_jvm_gc_seconds_total", "counter"),
             "search": ("es_search_requests_total", "counter"), "indexing": ("es_indexing_documents_total", "counter"),
             "rejections": ("es_search_thread_pool_rejections_total", "counter")}
    lines = []
    for key, (name, kind) in specs.items():
        lines.extend([f"# HELP {name} Simulated Elasticsearch {key}.", f"# TYPE {name} {kind}"])
        for node in NODES:
            v = values(node, now-state["start"], state["scenario"], now-state["since"])
            value = counters[node][key] if kind == "counter" else v[key]
            lines.append(f'{name}{{cluster="demo-es",node="{node}"}} {value:.6f}')
    name = "es_search_duration_seconds"
    lines.extend([f"# HELP {name} Simulated search duration.", f"# TYPE {name} histogram"])
    for node in NODES:
        labels = f'cluster="demo-es",node="{node}"'
        for b in BUCKETS:
            le = "+Inf" if math.isinf(b) else str(b)
            lines.append(f'{name}_bucket{{{labels},le="{le}"}} {counters[node][str(b)]:.6f}')
        lines.extend([f'{name}_sum{{{labels}}} {counters[node]["sum"]:.6f}', f'{name}_count{{{labels}}} {counters[node]["search"]:.6f}'])
    return PlainTextResponse("\n".join(lines)+"\n", media_type="text/plain; version=0.0.4")
