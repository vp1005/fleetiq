# 001. Python everywhere — Accepted

## Context

We need to choose languages for several services: gpu-simulator, collection
agent, fleet-api, redfish-mock, remediation-engine. The user is comfortable in
Python and REST APIs but new to monitoring infra. Goal is depth of learning,
not maximum resume keywords.

## Options considered

- **Python everywhere.** Fast to write, single language, user already knows it.
  Cons: doesn't show C++/Go skill.
- **Mixed (Python + Go for agent).** Go is the cloud-native lingua franca.
  Cons: doubles the learning load when the goal is infra concepts.
- **C++ for the agent from day 1.** Closest to the firmware-engineer JD bullet.
  Cons: huge time tax for marginal V1 benefit.

## Decision

Python everywhere for V1. We'll consider rewriting just the collection-agent
in Go or C++ as a V2 module *after* the full pipeline works end-to-end.

## Consequences

- **Easier.** Faster iteration, single dependency model, single test framework.
  Concept-learning isn't bottlenecked on language ergonomics.
- **Harder later.** When/if we add the C++ agent, we'll have to set up CMake,
  gtest, Conan/vcpkg. Plan for ~1 extra week.
- **Resume note.** The infra skills (Prometheus, Grafana, Alertmanager, Redfish,
  k3s) are language-agnostic and transfer cleanly. The Python is the vehicle,
  not the destination.
