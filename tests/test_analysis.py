import math
import pytest
from backend.analysis import statistics, anomalies, correlation, trend, normalize
from backend.grafana import interpolate, time_range
from demo.simulation import fixture


def make(values, times=None, **kwargs):
    return {"id": "sample", "metric": "unknown", "labels": {}, "points": list(zip(times or range(len(values)), values)), **kwargs}


def test_statistics():
    result = statistics(make([1, 2, 3, 4, 5]))
    assert result["average"] == 3
    assert result["stddev"] == pytest.approx(math.sqrt(2))
    assert result["p95"] == pytest.approx(4.8)
    assert (result["min"], result["max"], result["change"]) == (1, 5, 4)


def test_counter_reset_and_missing_samples():
    p = normalize([[0, 10], [2, 14], [4, 2], [6, 8]], "counter")
    assert p[:, 1].tolist() == [2, 1, 3]
    assert statistics(make([None, float("nan"), 4]))["count"] == 1


def test_correlation_aligns_timestamps():
    assert correlation(make([1, 2, 3]), make([2, 4, 6]))["pearson"] == pytest.approx(1)
    assert correlation(make([1, 2, 3]), make([6, 4, 2]))["pearson"] == pytest.approx(-1)
    assert correlation(make([1, 2, 3]), make([3, 5, 7], [10, 11, 12]))["pearson"] is None
    assert correlation(make([1, 1, 1]), make([2, 3, 4]))["pearson"] is None


@pytest.mark.parametrize("scenario,expected", [("normal", set()), ("jvm_pressure", {"heap", "gc", "latency"}), ("search_degradation", {"latency", "rejections"})])
def test_scenarios(scenario, expected):
    issues = [i for s in fixture(scenario) for i in anomalies(s)["issues"]]
    assert expected <= {i["metric"] for i in issues}
    if scenario == "normal":
        assert issues == []
    else:
        assert all(i["node"] == "es-node-2" for i in issues)
        by_id = {s["id"]: s for s in fixture(scenario)}
        for issue in issues:
            assert issue["peak"] == max(v for _, v in by_id[issue["series_id"]]["points"])


def test_trends_spikes_and_drops():
    assert trend(make(list(range(30))))["trend"] == "increasing"
    assert trend(make(list(reversed(range(30)))))["trend"] == "decreasing"
    assert trend(make([2]*30))["trend"] == "stable"
    assert anomalies(make([10]*20 + [100]*4))["issues"]
    drop = anomalies(make([10]*20 + [0]*4))["issues"][0]
    assert drop["title"] == "Unusual drop"
    assert drop["evidence_value"] == 0
    assert drop["evidence_label"] == "minimum"
    assert anomalies(make([10]))["insufficient_data"]


def test_variable_interpolation():
    assert interpolate('${cluster:regex}/$node/$__rate_interval', {"cluster": ["a", "b"], "node": "$__all"}, 5) == 'a|b/.*/20s'
    assert interpolate('${node:regex}', {"node": 'a.b"x'}) == 'a\\\\.b\\"x'
    assert interpolate('node="$node"', {"node": 'a.b'}) == 'node="a.b"'
    with pytest.raises(ValueError, match="Unresolved"):
        interpolate('$missing', {})
    with pytest.raises(ValueError, match="Raw"):
        interpolate('${node:raw}', {"node": "x"})
    with pytest.raises(ValueError):
        time_range("now-2d", "now")


def test_grafana_display_units():
    assert not anomalies(make([50]*10, metric="heap", unit="percent"))["issues"]
    assert anomalies(make([94]*10, metric="heap", unit="percent"))["issues"][0]["threshold"] == 85
    assert not anomalies(make([80]*10, metric="latency", unit="ms"))["issues"]
    assert anomalies(make([800]*10, metric="latency", unit="ms"))["issues"]
