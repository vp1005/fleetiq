# Per-Module Workflow

Every module follows the same six-phase rhythm. Boring on purpose — boring is
what lets you focus on understanding, not process.

## The six phases

### Phase 1 — Trade-off discussion (no code)

I lay out 2-3 reasonable design choices for this module, the pros and cons of
each, and recommend one. You agree, push back, or pick differently.

**Your job.** Read each option. Ask "why not C?" if a third option seems
obvious. Don't just rubber-stamp my recommendation — challenge it.

**Output.** Decisions captured as one-line bullets in `docs/decisions/NNN-*.md`.

---

### Phase 2 — Tools check

I tell you what new tools/libraries this module needs. You install them and
confirm before any code is written.

**Your job.** Run the install commands. Verify versions. Tell me if anything
errors out — we don't move forward with broken tools.

---

### Phase 3 — Concept walkthrough (still no code)

I explain what the module does internally — data flow, key concepts, why it's
structured this way.

**Your job.** Skim. If a concept feels fuzzy ("what's a histogram again?"),
say so before code. Cheaper to clarify here than mid-debug.

---

### Phase 4 — Code, in small chunks

I write the module file by file. After each file, you can ask "why this line?"
or "what does this do?"

**Your job.** Read each file before running it. Don't paste-and-pray. If a line
is opaque, ask.

---

### Phase 5 — Run + verify

You boot the module, hit it with `curl` or whatever, see it work. We add tests.
If something breaks, we debug together.

**Your job.** Actually run it locally. Reproduce every output. Try the "ways to
break it" suggestions at the end of each module.

---

### Phase 6 — Recap + commit

What you built. What concepts you now own. What's next. Commit to git.

**Your job.** Write a one-line journal entry: "Today I learned X." Sounds silly,
huge for retention. Commit with a clear message.

---

## Daily dev loop (once we're rolling)

```bash
cd ~/projects/fleetiq
git pull                       # if you've been on another machine

# Terminal 1: boot the stack (later modules)
docker compose up

# Terminal 2: edit code
code .                         # opens VS Code

# Terminal 3: test as you go
curl http://localhost:8001/api/v1/gpu | jq
pytest services/gpu-simulator/

# End of session
git add .
git commit -m "module N: <what you did>"
git push
```

## Conventions we'll hold ourselves to

- **One service per folder.** Each has its own `main.py`, `requirements.txt`,
  `Dockerfile`, `tests/`.
- **One ADR per major decision.** Format below.
- **All services speak HTTP + JSON.** No exotic protocols.
- **No service has hardcoded URLs to other services.** Everything's
  configurable via environment variables.
- **Every service has a `/health` endpoint** — for k3s liveness probes later.
- **Every service has `/docs` (FastAPI's auto-generated OpenAPI page).**

## ADR format (`docs/decisions/NNN-title.md`)

```markdown
# NNN. Title — Status (accepted / superseded)

## Context
What forced the decision? What constraints?

## Options considered
- A — pros / cons
- B — pros / cons

## Decision
We chose X because Y.

## Consequences
What does this make easier? Harder?
```

Real teams keep ADRs. By the end of the project you'll have ~10 of them — gold
for interview conversations ("walk me through a design decision you made").

## When you get stuck

Order of operations:
1. Re-read the error message carefully
2. Check the relevant service's logs (`docker compose logs <service>`)
3. Try to reproduce in isolation (can you `curl` the broken endpoint by itself?)
4. Ask. Don't grind for >30 minutes — the goal is learning, not pain.

## Definition of "module complete"

Before we move to module N+1, all of these must be true:
- [ ] Service runs locally without errors
- [ ] At least one test passes (`pytest`)
- [ ] You can explain in one sentence what each file does
- [ ] An ADR exists in `docs/decisions/` for any non-obvious choice
- [ ] Code is committed with a clear message
- [ ] README's status table updated
