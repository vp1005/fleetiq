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

(Filled in after module 1 is done.)
