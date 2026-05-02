# 002. Prometheus only (skip InfluxDB for V1) — Accepted

## Context

The original stack proposal had both Prometheus and InfluxDB. The user is new
to time-series databases. Goal is to learn the monitoring model deeply, not
collect tools.

## Options considered

- **Prometheus only.** Pull-based, simple model, industry-standard for
  cloud-native monitoring. PromQL learnable in an afternoon.
- **InfluxDB only.** Push-based, more database-like. Different query language
  (Flux). Less cloud-native ecosystem integration (no Alertmanager equivalent
  out of the box).
- **Both.** Demonstrates dual-stack experience. Doubles learning load.

## Decision

Prometheus only for V1. We can add InfluxDB later as a V2 module purely for
"long-term retention + analytics" — different role, no overlap.

## Consequences

- **Easier.** One time-series mental model. One query language. Native
  integration with Alertmanager and Grafana.
- **Harder later.** If we want the dual-stack story for portfolio, that's a
  separate week of work.
- **Lesson sequencing.** Pull model is easier to grasp first; push model is a
  natural V2 extension.
