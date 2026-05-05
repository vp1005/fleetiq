import asyncio
import os
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

GPU_ID = os.environ.get("GPU_ID", "GPU-0")
GPU_MODEL = os.environ.get("GPU_MODEL", "NVIDIA-H100-Mock")
MEM_TOTAL_MB = 81920

TICK_INTERVAL_S = 1.0
SMOOTHING_ALPHA = 0.3

THERMAL_RUNAWAY_RATE_C_PER_S = 1.0
THERMAL_RUNAWAY_MAX_OFFSET_C = 40.0
ECC_STORM_MEAN_PER_S = 8

WorkloadMode = Literal["idle", "training", "inference"]
FaultName = Literal[
    "thermal_runaway", "ecc_storm", "ecc_uncorrected", "gpu_drop", "nvlink_flap"
]

WORKLOAD_TARGETS: dict[str, dict[str, float]] = {
    "idle":      {"temp": 35.0, "power":  50.0, "util":  5.0, "nvlink":  50.0},
    "training":  {"temp": 75.0, "power": 350.0, "util": 95.0, "nvlink": 600.0},
    "inference": {"temp": 60.0, "power": 200.0, "util": 60.0, "nvlink": 300.0},
}


@dataclass
class GpuState:
    gpu_id: str
    workload_mode: str = "idle"
    temp_c: float = 35.0
    power_w: float = 50.0
    util_pct: float = 5.0
    mem_used_mb: float = 1024.0
    nvlink_bw_gbps: float = 50.0
    ecc_corrected_total: int = 0
    ecc_uncorrected_total: int = 0
    alive: bool = True
    active_faults: set[str] = field(default_factory=set)
    thermal_runaway_offset_c: float = 0.0


def smooth(actual: float, target: float, alpha: float = SMOOTHING_ALPHA) -> float:
    return actual + alpha * (target - actual)


def advance(state: GpuState, dt: float) -> None:
    if not state.alive:
        return

    target = WORKLOAD_TARGETS[state.workload_mode]
    state.temp_c = smooth(state.temp_c, target["temp"])
    state.power_w = smooth(state.power_w, target["power"])
    state.util_pct = smooth(state.util_pct, target["util"])
    state.nvlink_bw_gbps = smooth(state.nvlink_bw_gbps, target["nvlink"])
    state.mem_used_mb = smooth(
        state.mem_used_mb, MEM_TOTAL_MB * (state.util_pct / 100.0) * 0.8
    )

    if "thermal_runaway" in state.active_faults:
        state.thermal_runaway_offset_c = min(
            THERMAL_RUNAWAY_MAX_OFFSET_C,
            state.thermal_runaway_offset_c + THERMAL_RUNAWAY_RATE_C_PER_S * dt,
        )
    elif state.thermal_runaway_offset_c > 0:
        state.thermal_runaway_offset_c = max(
            0.0, state.thermal_runaway_offset_c - THERMAL_RUNAWAY_RATE_C_PER_S * dt
        )

    if "ecc_storm" in state.active_faults:
        burst = random.randint(
            max(0, ECC_STORM_MEAN_PER_S - 4), ECC_STORM_MEAN_PER_S + 4
        )
        state.ecc_corrected_total += burst

    if "nvlink_flap" in state.active_faults:
        state.nvlink_bw_gbps = 0.0


def reported_temp(state: GpuState) -> float:
    return state.temp_c + state.thermal_runaway_offset_c


async def tick_loop(state: GpuState) -> None:
    while True:
        try:
            advance(state, dt=TICK_INTERVAL_S)
        except Exception as exc:
            print(f"[gpu-simulator] tick error: {exc!r}")
        await asyncio.sleep(TICK_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = GpuState(gpu_id=GPU_ID)
    app.state.gpu = state
    task = asyncio.create_task(tick_loop(state))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=f"gpu-simulator [{GPU_ID}]", lifespan=lifespan)


class Telemetry(BaseModel):
    gpu_id: str
    model: str
    workload_mode: str
    temp_c: float
    power_w: float
    util_pct: float
    mem_used_mb: float
    mem_total_mb: int
    nvlink_bw_gbps: float
    ecc_corrected_total: int
    ecc_uncorrected_total: int
    active_faults: list[str]


@app.get("/health")
def health():
    state: GpuState = app.state.gpu
    if not state.alive:
        raise HTTPException(status_code=503, detail="gpu unreachable")
    return {"status": "ok", "gpu_id": state.gpu_id}


@app.get("/api/v1/gpu", response_model=Telemetry)
def get_gpu():
    state: GpuState = app.state.gpu
    if not state.alive:
        raise HTTPException(status_code=503, detail="gpu unreachable")
    return Telemetry(
        gpu_id=state.gpu_id,
        model=GPU_MODEL,
        workload_mode=state.workload_mode,
        temp_c=round(reported_temp(state), 2),
        power_w=round(state.power_w, 2),
        util_pct=round(state.util_pct, 2),
        mem_used_mb=round(state.mem_used_mb, 2),
        mem_total_mb=MEM_TOTAL_MB,
        nvlink_bw_gbps=round(state.nvlink_bw_gbps, 2),
        ecc_corrected_total=state.ecc_corrected_total,
        ecc_uncorrected_total=state.ecc_uncorrected_total,
        active_faults=sorted(state.active_faults),
    )


@app.post("/api/v1/workload/{mode}")
def set_workload(mode: WorkloadMode):
    state: GpuState = app.state.gpu
    state.workload_mode = mode
    return {"workload_mode": mode}


# Must be declared BEFORE /api/v1/fault/{fault} — FastAPI matches routes in
# declaration order, and the path-param route would swallow "clear" first.
@app.post("/api/v1/fault/clear")
def clear_faults():
    state: GpuState = app.state.gpu
    state.active_faults.clear()
    state.alive = True
    return {"active_faults": []}


@app.post("/api/v1/fault/{fault}")
def inject_fault(fault: FaultName):
    state: GpuState = app.state.gpu
    if fault == "gpu_drop":
        state.alive = False
        state.active_faults.add("gpu_drop")
    elif fault == "ecc_uncorrected":
        state.ecc_uncorrected_total += 1
    else:
        state.active_faults.add(fault)
    return {"injected": fault, "active_faults": sorted(state.active_faults)}
