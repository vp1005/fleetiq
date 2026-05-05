# 003. gpu-simulator: tick model, fault composition, state shape — Accepted

## Context

Module 1 (gpu-simulator) needs three small architectural choices before code is
written:

1. How does telemetry advance over time?
2. How do workload modes and faults compose?
3. Where does the simulator's mutable state live?

These decisions shape every later module: the collection-agent will scrape this,
the remediation-engine will trigger faults on it, and Prometheus alerts will
fire on the values it produces. Getting them right (and explainable) now saves
rework.

## Options considered

### Tick model

- **A. Background async task.** A coroutine started in FastAPI's `lifespan`
  wakes every 1s and mutates state in place. GET handlers read the current
  snapshot. Pros: matches real hardware (telemetry exists whether or not anyone
  reads it); ECC bursts and thermal ramps are easy to express as "per-tick"
  rules; teaches `lifespan` and `asyncio.create_task`, which we'll reuse.
  Cons: background mutation needs care (in single-process FastAPI on one event
  loop, this is fine — no GIL races, just be deliberate about ordering).
- **B. Lazy compute on request.** No loop. Each GET computes "given last
  update_ts and elapsed Δt, what would the value be now?" Pros: stateless-ish,
  no concurrency to reason about. Cons: bursty faults (ECC storms) require
  reconstructing burst history per call; awkward; skips the lifespan concept.

### Workload + fault composition

- **A. Workload sets a target; faults mutate the target or the trajectory.**
  Each workload mode (idle / training / inference) defines target temp, power,
  utilisation. A smoothing function pulls the actual value toward the target
  each tick. Faults then either change the target (`thermal_runaway` adds a
  drifting offset) or override a specific signal (`gpu_drop` flips a flag the
  `/health` route reads). Composes cleanly when multiple faults are active.
- **B. Faults overwrite output values directly.** Simpler at first, but breaks
  down with concurrent faults that both want to "own" a value.

### State shape

- **A. `@dataclass GpuState` held on `app.state.gpu`.** Mutable, fast, no
  validation overhead per tick. Pydantic models used only for HTTP *responses*
  (where validation is cheap and useful as a contract).
- **B. Pydantic model for everything.** Cleaner uniformity, but every tick
  pays validation cost and every mutation needs `model_copy(update=…)` or a
  mutable `BaseModel`, which is awkward.

## Decision

- Tick model → **A** (1 Hz background async task in `lifespan`).
- Composition → **A** (workload = target; faults = trajectory mutators or
  signal overrides).
- State shape → **A** (dataclass on `app.state`, Pydantic for responses only).

## Consequences

- **Easier.** Faults like `thermal_runaway` (+1°C/s) and `ecc_storm`
  (Poisson-ish bursts) become a few lines in the tick function. `/health` and
  `/api/v1/gpu` are trivial reads. We learn `lifespan` once and reuse it in
  modules 2, 5, 6, 7.
- **Harder.** We have to be careful that the tick task doesn't crash silently
  (wrap the loop body in try/except + log). We also need the tick to keep
  running even when no requests arrive — that's exactly what `lifespan` is for,
  but it's a new concept.
- **Future-proof.** When module 8 puts this in k3s as 50 replicas, each pod
  runs its own tick loop. No shared state, no coordination needed. Good.
