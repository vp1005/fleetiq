# gpu-simulator

**Module 1.** Fakes a single NVIDIA GPU for testing the rest of the stack
without real hardware. One process = one GPU. Run multiple to fake a fleet.

## Files (will be added in module 1)

- `main.py` — the FastAPI app
- `requirements.txt` — Python deps
- `Dockerfile` — for Docker Compose
- `tests/test_simulator.py` — pytest suite

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
GPU_ID=GPU-1 uvicorn main:app --reload --port 8001
```

## API

| Method | Path                        | Purpose                       |
|--------|-----------------------------|-------------------------------|
| GET    | `/health`                   | Liveness — 503 if "dead"      |
| GET    | `/api/v1/gpu`               | Current telemetry snapshot    |
| POST   | `/api/v1/workload/{mode}`   | idle / training / inference   |
| POST   | `/api/v1/fault/{fault}`     | inject a fault                |
| POST   | `/api/v1/fault/clear`       | clear all faults              |
| GET    | `/docs`                     | auto-generated OpenAPI page   |

## Faults supported

- `thermal_runaway` — temp climbs +1°C/sec up to +40°C
- `ecc_storm` — bursty corrected ECC errors
- `ecc_uncorrected` — single uncorrected ECC error (severe)
- `gpu_drop` — GPU stops responding (HTTP 503)
- `nvlink_flap` — NVLink bandwidth drops to 0
