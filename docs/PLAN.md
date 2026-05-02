# FleetIQ — Build Plan

Nine modules, built one at a time. Each module ends with something visibly more
impressive than the last. We don't move on until the current module is solid
and you understand it.

## Guiding principles

- **Depth over breadth.** Better to ship 5 modules deeply than 9 shallowly.
- **Run everything yourself.** Reproduce every output locally.
- **Commit after each module.** Working state goes into git.
- **Break things on purpose.** Each module ends with "ways to break it."
- **One ADR per major trade-off.** Lives in `docs/decisions/`.

---

## Module 1 — gpu-simulator

**Goal.** A REST service that pretends to be a single NVIDIA GPU, emitting
realistic time-varying telemetry with workload modes and fault injection.

**Why first.** Foundation. Every other module reads from this. Without
fault injection here, modules 4–7 have nothing to react to.

**Tech.** Python 3.12, FastAPI, uvicorn.

**Concepts you'll meet.** REST endpoints, FastAPI decorators, async lifespan
tasks, exponential smoothing, route ordering, dataclasses, Pydantic validation.

**Demoable outcome.** `curl` a fake GPU, change its workload, inject thermal
runaway, drop it, watch it return 503.

---

## Module 2 — collection-agent

**Goal.** A service that polls every gpu-simulator on a schedule, translates
their JSON into Prometheus's text format, and exposes a single `/metrics`
endpoint that Prometheus scrapes.

**Why second.** First contact with the Prometheus data model. Teaches the
"translate from native format to Prometheus format" pattern that
`dcgm-exporter`, `node-exporter`, and every real Prometheus exporter follows.

**Tech.** Python, `prometheus_client`, `httpx` (async HTTP client).

**Concepts you'll meet.** Pull-based monitoring, gauges vs counters vs
histograms, label cardinality, the `up` metric pattern, async polling.

**Demoable outcome.** `curl http://agent/metrics` returns dozens of correctly
formatted Prometheus metrics for the whole fleet.

---

## Module 3 — Prometheus + Grafana

**Goal.** Stand up Prometheus to scrape the agent and Grafana to visualize.
Build the first dashboard: fleet overview heatmap + per-GPU deep-dive.

**Why third.** First *visible* end-to-end win. Once you see your fake fleet
on a real Grafana dashboard, the project starts to feel real.

**Tech.** Prometheus + Grafana via Docker Compose. PromQL for queries,
Grafana's dashboard JSON.

**Concepts you'll meet.** Scrape configs, PromQL basics (rate, avg by, etc.),
Grafana panels and variables, dashboard-as-code.

**Demoable outcome.** Live Grafana dashboard. Inject a fault and watch it
appear on the graph in real time.

---

## Module 4 — Alertmanager + alert rules

**Goal.** Define Prometheus alerts (`gpu_temp_critical`, `gpu_unreachable`,
`ecc_uncorrected_error`). Route them through Alertmanager to a webhook
receiver.

**Why fourth.** Closes the *detection* loop. Now the system notices problems
without you watching the dashboard.

**Tech.** Prometheus alerting rules (YAML), Alertmanager config (YAML),
webhook receiver (a small FastAPI app to print alerts).

**Concepts you'll meet.** Alert rules with `for:` durations, severity labels,
Alertmanager grouping/inhibition/silencing, webhook payload schema.

**Demoable outcome.** Inject thermal runaway. Within 60s, your webhook
receiver prints the alert payload.

---

## Module 5 — redfish-mock

**Goal.** A FastAPI service implementing a useful subset of the DMTF Redfish
schema — the standard out-of-band management API. Simulates the BMC chip on
a real server.

**Why fifth.** Adds the "command" dimension. Until now, the system can only
*read*; Redfish lets it *act* (reset chassis, change power cap).

**Tech.** Python, FastAPI, Pydantic for strict schema validation.

**Concepts you'll meet.** Out-of-band vs in-band, Redfish resource hierarchy,
HTTP PATCH for partial updates, schema specs as a contract.

**Demoable outcome.** `curl` Redfish endpoints to read chassis power and
trigger a system reset.

---

## Module 6 — fleet-api

**Goal.** A single API that aggregates the whole fleet. `GET /nodes`,
`GET /nodes/{id}/telemetry`, `POST /nodes/{id}/remediate`. The human (and the
remediation engine) interact with this instead of individual simulators.

**Why sixth.** Aggregation layer. Real fleet managers expose one API even
though the data comes from many sources.

**Tech.** Python, FastAPI, `httpx`.

**Concepts you'll meet.** API gateway pattern, fan-out queries, error
aggregation when one node is down.

**Demoable outcome.** One API call returns a snapshot of the whole fleet.

---

## Module 7 — remediation-engine

**Goal.** Receive Alertmanager webhooks. Look up `(alert × severity) → action`
in a policy table. Execute the action via fleet-api or redfish-mock. Escalate
to PagerDuty (mock) if recovery fails.

**Why seventh.** *The* demo moment. The whole project exists for this:
inject fault → detect → decide → fix → verify, all without human input.

**Tech.** Python, FastAPI, `httpx`. Policy table starts as YAML, simple.

**Concepts you'll meet.** Webhook receivers, policy engines, idempotency,
retry/timeout semantics, recovery verification.

**Demoable outcome.** End-to-end auto-remediation video — record this for
your portfolio.

---

## Module 8 — k3s migration

**Goal.** Take the same stack and run it on local Kubernetes (k3s). Scale the
simulator fleet to 50+ nodes via a single replica-count change.

**Why eighth.** Real fleets run on Kubernetes. This module turns "small demo"
into "scale story."

**Tech.** k3s (or k3d / kind), kubectl, Helm (optional), ServiceMonitor for
Prometheus auto-discovery.

**Concepts you'll meet.** Deployments, Services, ConfigMaps, ServiceMonitor
CRDs, resource limits, horizontal scaling.

**Demoable outcome.** `kubectl scale deploy gpu-simulator --replicas=50` and
watch Prometheus auto-discover them all.

---

## Module 9 — ML detector (optional, stretch)

**Goal.** Predict failures before they cross thresholds. Train an Isolation
Forest on historical fleet data; emit anomaly scores back to Prometheus.

**Why optional.** Nice-to-have for portfolio depth. Skip if time is short.

**Tech.** Python, scikit-learn, NumPy, Prometheus push gateway.

**Concepts you'll meet.** Multivariate anomaly detection, training/serving
split, pushing custom metrics to Prometheus.

**Demoable outcome.** Predictive alert fires *before* threshold breach.

---

## After module 9

- Architecture spec PDF (the JD asked for this — write it)
- Demo video, 3 minutes, recorded fault drill
- README polished with screenshots
- ADRs cleaned up in `docs/decisions/`
- Push to GitHub, link from resume
