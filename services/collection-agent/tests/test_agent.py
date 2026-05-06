import pytest
import httpx
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

import main
from main import _registry, app, poll_once

SAMPLE_TELEMETRY = {
    "gpu_id": "GPU-0",
    "model": "NVIDIA-H100-Mock",
    "workload_mode": "idle",
    "temp_c": 42.5,
    "power_w": 80.0,
    "util_pct": 10.0,
    "mem_used_mb": 2048.0,
    "mem_total_mb": 81920,
    "nvlink_bw_gbps": 100.0,
    "ecc_corrected_total": 3,
    "ecc_uncorrected_total": 1,
    "active_faults": [],
}


@pytest.fixture(autouse=True)
def reset_module_state():
    main._cache.clear()
    main._url_to_gpu_id.clear()
    yield
    main._cache.clear()
    main._url_to_gpu_id.clear()


# ---------- poll_once unit tests ----------

async def test_poll_once_populates_cache_on_success():
    def handler(request):
        return httpx.Response(200, json=SAMPLE_TELEMETRY)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await poll_once(client, "http://sim-0:8001")

    assert main._cache["GPU-0"] == SAMPLE_TELEMETRY
    assert main._url_to_gpu_id["http://sim-0:8001"] == "GPU-0"


async def test_poll_once_marks_gpu_down_after_known_failure():
    main._url_to_gpu_id["http://sim-0:8001"] = "GPU-0"
    main._cache["GPU-0"] = SAMPLE_TELEMETRY

    def handler(request):
        return httpx.Response(503, text="gpu unreachable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await poll_once(client, "http://sim-0:8001")

    assert main._cache["GPU-0"] is None


async def test_poll_once_leaves_cache_empty_for_never_seen_failing_url():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await poll_once(client, "http://unknown:9999")

    assert len(main._cache) == 0
    assert len(main._url_to_gpu_id) == 0


async def test_poll_once_overwrites_down_entry_on_recovery():
    main._url_to_gpu_id["http://sim-0:8001"] = "GPU-0"
    main._cache["GPU-0"] = None

    def handler(request):
        return httpx.Response(200, json=SAMPLE_TELEMETRY)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await poll_once(client, "http://sim-0:8001")

    assert main._cache["GPU-0"] == SAMPLE_TELEMETRY


# ---------- GpuCollector unit tests ----------

def _metrics_text() -> str:
    return generate_latest(_registry).decode()


def test_collector_emits_temperature_for_healthy_gpu():
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    output = _metrics_text()
    assert "gpu_temperature_celsius" in output
    assert 'gpu_id="GPU-0"' in output
    assert "42.5" in output


def test_collector_emits_memory_converted_to_bytes():
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    output = _metrics_text()
    assert "gpu_memory_used_bytes" in output
    # 2048 MB * 1048576 = 2147483648 bytes — prometheus_client uses scientific notation
    assert "2.147483648e+09" in output


def test_collector_emits_nvlink_bandwidth_metric():
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    output = _metrics_text()
    assert "gpu_nvlink_bandwidth_bytes_per_second" in output


def test_collector_emits_ecc_counters():
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    output = _metrics_text()
    assert "gpu_ecc_errors_corrected_total" in output
    assert "gpu_ecc_errors_uncorrected_total" in output


def test_collector_emits_gpu_up_1_when_healthy():
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    output = _metrics_text()
    assert 'gpu_up{gpu_id="GPU-0"} 1.0' in output


def test_collector_emits_gpu_up_0_when_down():
    main._cache["GPU-0"] = None
    output = _metrics_text()
    assert 'gpu_up{gpu_id="GPU-0"} 0.0' in output


def test_collector_omits_telemetry_metrics_when_gpu_is_down():
    main._cache["GPU-0"] = None
    output = _metrics_text()
    # Temperature metric should have no samples (GPU-0 down means no label set)
    assert 'gpu_temperature_celsius{gpu_id="GPU-0"' not in output


def test_collector_handles_empty_cache_gracefully():
    output = _metrics_text()
    assert "gpu_up" in output  # metric family header still present
    assert 'gpu_id="GPU-0"' not in output


def test_collector_tracks_multiple_gpus():
    second = {**SAMPLE_TELEMETRY, "gpu_id": "GPU-1", "temp_c": 55.0}
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    main._cache["GPU-1"] = second
    output = _metrics_text()
    assert 'gpu_id="GPU-0"' in output
    assert 'gpu_id="GPU-1"' in output


# ---------- HTTP endpoint tests ----------

def test_health_returns_200():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_metrics_returns_200_with_prometheus_content_type():
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_metrics_endpoint_includes_gpu_up_for_cached_gpu():
    main._cache["GPU-0"] = SAMPLE_TELEMETRY
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert 'gpu_up{gpu_id="GPU-0"} 1.0' in resp.text


def test_metrics_endpoint_reflects_down_gpu():
    main._cache["GPU-0"] = None
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert 'gpu_up{gpu_id="GPU-0"} 0.0' in resp.text
