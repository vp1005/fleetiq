import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

SIMULATOR_URLS: list[str] = [
    u.strip()
    for u in os.environ.get("SIMULATOR_URLS", "http://localhost:8001").split(",")
    if u.strip()
]
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "5"))

# gpu_id -> telemetry dict, or None if the GPU was reachable before but is now down
_cache: dict[str, dict | None] = {}
# simulator URL -> gpu_id (populated after first successful poll)
_url_to_gpu_id: dict[str, str] = {}


class GpuCollector:
    """Custom Prometheus collector that translates cached GPU telemetry to metric families."""

    def collect(self):
        temp = GaugeMetricFamily(
            "gpu_temperature_celsius", "GPU temperature in Celsius",
            labels=["gpu_id", "model"],
        )
        power = GaugeMetricFamily(
            "gpu_power_watts", "GPU power draw in watts",
            labels=["gpu_id", "model"],
        )
        util = GaugeMetricFamily(
            "gpu_utilization_percent", "GPU utilization percentage (0–100)",
            labels=["gpu_id", "model"],
        )
        mem_used = GaugeMetricFamily(
            "gpu_memory_used_bytes", "GPU memory in use, bytes",
            labels=["gpu_id", "model"],
        )
        mem_total = GaugeMetricFamily(
            "gpu_memory_total_bytes", "GPU total memory, bytes",
            labels=["gpu_id", "model"],
        )
        nvlink = GaugeMetricFamily(
            "gpu_nvlink_bandwidth_bytes_per_second",
            "NVLink aggregate bandwidth, bytes per second",
            labels=["gpu_id", "model"],
        )
        # CounterMetricFamily auto-appends _total to the metric name in exposition
        ecc_corrected = CounterMetricFamily(
            "gpu_ecc_errors_corrected", "Cumulative corrected ECC errors",
            labels=["gpu_id", "model"],
        )
        ecc_uncorrected = CounterMetricFamily(
            "gpu_ecc_errors_uncorrected", "Cumulative uncorrected ECC errors",
            labels=["gpu_id", "model"],
        )
        up = GaugeMetricFamily(
            "gpu_up", "1 if the GPU simulator is reachable, 0 otherwise",
            labels=["gpu_id"],
        )

        for gpu_id, data in list(_cache.items()):
            if data is not None:
                lbl = [data["gpu_id"], data["model"]]
                temp.add_metric(lbl, data["temp_c"])
                power.add_metric(lbl, data["power_w"])
                util.add_metric(lbl, data["util_pct"])
                mem_used.add_metric(lbl, data["mem_used_mb"] * 1_048_576)
                mem_total.add_metric(lbl, data["mem_total_mb"] * 1_048_576)
                nvlink.add_metric(lbl, data["nvlink_bw_gbps"] * 1e9)
                ecc_corrected.add_metric(lbl, data["ecc_corrected_total"])
                ecc_uncorrected.add_metric(lbl, data["ecc_uncorrected_total"])
                up.add_metric([gpu_id], 1.0)
            else:
                up.add_metric([gpu_id], 0.0)

        yield temp
        yield power
        yield util
        yield mem_used
        yield mem_total
        yield nvlink
        yield ecc_corrected
        yield ecc_uncorrected
        yield up


# Separate registry avoids including default process/platform metrics
_registry = CollectorRegistry()
_registry.register(GpuCollector())


async def poll_once(client: httpx.AsyncClient, url: str) -> None:
    """Poll a single gpu-simulator URL and update the cache."""
    try:
        resp = await client.get(f"{url}/api/v1/gpu", timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
        gpu_id = data["gpu_id"]
        _url_to_gpu_id[url] = gpu_id
        _cache[gpu_id] = data
    except Exception:
        gpu_id = _url_to_gpu_id.get(url)
        if gpu_id is not None:
            _cache[gpu_id] = None


async def poll_loop() -> None:
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.gather(
                *[poll_once(client, url) for url in SIMULATOR_URLS],
                return_exceptions=True,
            )
            await asyncio.sleep(POLL_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="collection-agent", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    output = generate_latest(_registry)
    return Response(
        content=output,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
