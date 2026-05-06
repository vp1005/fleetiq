# FleetIQ

A learning project: build a GPU fleet telemetry & auto-remediation platform from
scratch, without GPU hardware. The goal is to deeply understand cloud-native
observability — Prometheus, Grafana, Alertmanager, Redfish, Kubernetes — by
building each piece by hand.

## Where to start

1. Read **`docs/PLAN.md`** — the full module-by-module build plan
2. Read **`docs/WORKFLOW.md`** — the dev rhythm we follow every module
3. Then jump into **`services/gpu-simulator/`** for module 1

## Project layout

```
fleetiq/
├── docs/
│   ├── PLAN.md                  ← what we're building, in what order
│   ├── WORKFLOW.md              ← the per-module process
│   ├── ARCHITECTURE.md          ← system design (grows over time)
│   └── decisions/               ← Architecture Decision Records (ADRs)
├── services/                    ← every service we write
│   ├── gpu-simulator/           ← module 1 — fakes a GPU
│   ├── collection-agent/        ← module 2 — speaks Prometheus
│   ├── fleet-api/               ← module 6 — fleet-wide control plane
│   ├── redfish-mock/            ← module 5 — out-of-band BMC mock
│   └── remediation-engine/      ← module 7 — auto-fix loop
├── infra/                       ← off-the-shelf infrastructure config
│   ├── prometheus/              ← module 3
│   ├── alertmanager/            ← module 4
│   └── grafana/                 ← module 3
├── k8s/                         ← module 8 — k3s manifests
├── scripts/                     ← helper scripts (smoke tests, fault drills)
├── docker-compose.yml           ← local dev stack — grows each module
└── README.md
```

## Status

| # | Module                  | Status      |
|---|-------------------------|-------------|
| 1 | gpu-simulator           | done        |
| 2 | collection-agent        | done        |
| 3 | Prometheus + Grafana    | done        |
| 4 | Alertmanager            | pending     |
| 5 | redfish-mock            | pending     |
| 6 | fleet-api               | pending     |
| 7 | remediation-engine      | pending     |
| 8 | k3s migration           | pending     |
| 9 | ML detector (optional)  | pending     |
