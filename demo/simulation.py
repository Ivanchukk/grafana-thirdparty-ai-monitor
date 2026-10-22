"""Deterministic metric relationships shared by the live exporter and test fixtures."""
import math

SCENARIOS = ("normal", "jvm_pressure", "search_degradation")
NODES = ("es-node-1", "es-node-2", "es-node-3")
BUCKETS = (.025, .05, .1, .25, .5, 1, 2.5, 5, float("inf"))


def values(node: str, elapsed: float, scenario: str = "normal", incident_age: float = 0) -> dict:
    """Returns gauges and counter rates. Incidents ramp over 40 seconds."""
    i = NODES.index(node)
    wave = math.sin(elapsed / 23 + i) * .025
    load = min(1., max(0., incident_age / 40)) if scenario != "normal" else 0
    affected = load if node == "es-node-2" else 0
    heap, cpu, latency, gc, volume, rejects = .51 + wave + i*.025, .31 + wave + i*.04, .065 + wave/3, .008, 90 + i*12 + wave*100, 0.
    if scenario == "jvm_pressure":
        heap += .39*affected
        cpu += .48*affected
        latency += .60*affected
        gc += .36*affected
    if scenario == "search_degradation":
        latency += .8*affected
        volume += 420*affected
        rejects += 16*affected
        cpu += .5*affected
    return {"cpu": cpu, "heap": heap, "gc": gc, "latency": latency,
            "search": volume, "indexing": 180 + i*15 + wave*200,
            "rejections": rejects, "memory": (8.2 + i*.3 + affected*2)*1024**3,
            "connections": 65 + i*8 + volume*.15, "up": 1.}


def fixture(scenario: str, points: int = 181) -> list[dict]:
    """Thirty minutes, 10-second resolution, incident in the final ten minutes."""
    end = 1_760_000_000
    result = []
    for metric in values(NODES[0], 0):
        for node in NODES:
            data = [[end - (points-1-i)*10, values(node, i*10, scenario, max(0, i*10-1200))[metric]] for i in range(points)]
            result.append({"id": f"{metric}:{node}", "metric": metric, "labels": {"node": node, "cluster": "demo-es"}, "points": data, "unit": "ratio"})
    return result
