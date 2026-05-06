# FleetIQ Architecture

This document grows as we build. After each module, we add a section describing
what was added, how it fits, and any quirks worth remembering.

## High-level vision

A simulated GPU fleet with full in-band + out-of-band telemetry, dual-purpose
storage (Prometheus for SLO monitoring), Grafana dashboards, alert-driven
auto-remediation, and an optional ML anomaly detector.

```
GPU sims  ─►  collection-agent  ─►  Prometheus  ─►  Grafana
                                          │
                                          ▼
                                    Alertmanager  ─►  remediation-engine
                                                            │
                                                            ▼
                                                     fleet-api / redfish-mock
                                                            │
                                                            ▼
                                                     (action on simulators)
```

## Service inventory

| Service              | Module | Port | Role                                 |
|----------------------|--------|------|--------------------------------------|
| gpu-simulator (×N)   | 1      | 8001+| Fakes one GPU; supports faults       |
| collection-agent     | 2      | 9100 | Polls sims, exposes Prom metrics     |
| Prometheus           | 3      | 9090 | Scrapes agent, stores time-series    |
| Grafana              | 3      | 3000 | Dashboards                           |
| Alertmanager         | 4      | 9093 | Alert routing                        |
| redfish-mock (×N)    | 5      | 8081+| Out-of-band BMC mock                 |
| fleet-api            | 6      | 8000 | Aggregated fleet API                 |
| remediation-engine   | 7      | 9500 | Webhook → policy → action            |

## In-band vs out-of-band

The single most important architectural concept in this project.

- **In-band.** Software on the host OS reads from the GPU driver. Rich data,
  fails when the host is broken. Modeled by `gpu-simulator`.
- **Out-of-band.** A separate management chip (BMC) reads chassis sensors and
  accepts commands over its own network. Coarser data, works even when the
  host is dead. Speaks Redfish. Modeled by `redfish-mock`.

A real fleet manager uses *both* because each sees things the other can't, and
only OOB can take action when the host is hung.

## Module-by-module additions

### Module 1 — gpu-simulator

A single FastAPI service (`services/gpu-simulator/main.py`) that simulates one
NVIDIA GPU. State is held in a `GpuState` dataclass and advanced by a 1 Hz
async tick loop using exponential smoothing (`alpha=0.3`) toward per-workload
target values. Fault injection (thermal runaway, ECC storm, NVLink flap,
gpu_drop) is applied on each tick. The `gpu_drop` fault sets `alive=False`,
causing all endpoints to return 503. The tick loop short-circuits when `alive`
is false so state doesn't drift while dropped.

Key implementation note: the `/api/v1/fault/clear` route must be declared
before `/api/v1/fault/{fault}` because FastAPI matches routes in declaration
order and the path-param route would otherwise swallow the literal `"clear"`.

### Module 2 — collection-agent

A FastAPI service (`services/collection-agent/main.py`) that acts as a
Prometheus exporter for the GPU fleet.

**Pull-based monitoring:** Prometheus scrapes the agent's `/metrics` endpoint on
demand. The agent does not push; it caches the latest telemetry from a
background poll loop and serves it whenever Prometheus asks.

**Polling:** An async `poll_loop` task starts with the FastAPI lifespan and
polls every simulator URL concurrently via `httpx.AsyncClient`. Each
`poll_once` call does a `GET /api/v1/gpu`; on success it writes the JSON into
`_cache[gpu_id]`; on failure it sets `_cache[gpu_id] = None` (if we've seen
that GPU before). URLs that have never responded successfully are silently
skipped — we can't emit `gpu_up=0` without knowing the `gpu_id` label.

**Custom collector:** Rather than using prometheus_client's default gauge/counter
objects (which require delta tracking for counters), the agent uses a custom
`GpuCollector` class registered on a private `CollectorRegistry`. Its
`collect()` method is called synchronously each time `generate_latest()` runs
and reads a `list()` snapshot of `_cache` — safe under asyncio's
single-threaded cooperative model. This is the same pattern real exporters
(`dcgm-exporter`, `node_exporter`) follow.

**Metric types used:**
- `GaugeMetricFamily` — temperature, power, utilization, memory, NVLink,
  and the `gpu_up` sentinel.
- `CounterMetricFamily` — ECC corrected/uncorrected totals. The library
  automatically appends `_total` to counter names in the exposition format.

**Unit conversions** follow Prometheus convention: memory in bytes (MB × 2²⁰),
NVLink bandwidth in bytes/s (Gbps × 10⁹).

**Config:** `SIMULATOR_URLS` (comma-separated, default `http://localhost:8001`)
and `POLL_INTERVAL_S` (default `5`) are environment variables.
