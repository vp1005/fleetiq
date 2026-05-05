from fastapi.testclient import TestClient

from main import GpuState, advance, app, reported_temp, smooth


# ---------- pure unit tests on the simulation core ----------

def test_smooth_moves_halfway_at_alpha_half():
    assert smooth(0.0, 100.0, alpha=0.5) == 50.0


def test_smooth_is_fixed_point_when_actual_equals_target():
    assert smooth(50.0, 50.0, alpha=0.5) == 50.0


def test_advance_pulls_signals_toward_workload_target():
    state = GpuState(gpu_id="t", workload_mode="training")
    for _ in range(50):
        advance(state, dt=1.0)
    assert abs(state.temp_c - 75.0) < 0.5
    assert abs(state.power_w - 350.0) < 1.0
    assert abs(state.util_pct - 95.0) < 0.5


def test_thermal_runaway_climbs_then_caps_at_max_offset():
    state = GpuState(gpu_id="t", workload_mode="idle")
    state.active_faults.add("thermal_runaway")
    for _ in range(60):
        advance(state, dt=1.0)
    assert state.thermal_runaway_offset_c == 40.0


def test_thermal_runaway_offset_decays_after_clear():
    state = GpuState(gpu_id="t", workload_mode="idle")
    state.active_faults.add("thermal_runaway")
    for _ in range(10):
        advance(state, dt=1.0)
    assert state.thermal_runaway_offset_c == 10.0
    state.active_faults.clear()
    for _ in range(5):
        advance(state, dt=1.0)
    assert state.thermal_runaway_offset_c == 5.0


def test_ecc_storm_increments_corrected_counter():
    state = GpuState(gpu_id="t")
    state.active_faults.add("ecc_storm")
    advance(state, dt=1.0)
    assert state.ecc_corrected_total > 0


def test_nvlink_flap_clamps_bandwidth_to_zero():
    state = GpuState(gpu_id="t", workload_mode="training")
    state.active_faults.add("nvlink_flap")
    for _ in range(5):
        advance(state, dt=1.0)
    assert state.nvlink_bw_gbps == 0.0


def test_advance_short_circuits_when_not_alive():
    state = GpuState(gpu_id="t", workload_mode="training", alive=False)
    initial = state.temp_c
    advance(state, dt=1.0)
    assert state.temp_c == initial


def test_reported_temp_includes_runaway_offset():
    state = GpuState(gpu_id="t", temp_c=50.0, thermal_runaway_offset_c=12.5)
    assert reported_temp(state) == 62.5


# ---------- HTTP integration tests through the FastAPI app ----------

def test_health_flips_503_on_drop_and_recovers_after_clear():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        client.post("/api/v1/fault/gpu_drop")
        assert client.get("/health").status_code == 503
        assert client.get("/api/v1/gpu").status_code == 503
        client.post("/api/v1/fault/clear")
        assert client.get("/health").status_code == 200


def test_workload_endpoint_validates_mode_via_pydantic():
    with TestClient(app) as client:
        assert client.post("/api/v1/workload/training").status_code == 200
        assert client.post("/api/v1/workload/mining").status_code == 422


def test_fault_clear_route_wins_over_path_param_route():
    with TestClient(app) as client:
        # If declaration order regresses, "clear" gets matched by /fault/{fault}
        # and Pydantic Literal validation rejects it with 422.
        assert client.post("/api/v1/fault/clear").status_code == 200


def test_invalid_fault_name_rejected_with_422():
    with TestClient(app) as client:
        assert client.post("/api/v1/fault/explode").status_code == 422


def test_telemetry_response_has_expected_fields():
    with TestClient(app) as client:
        body = client.get("/api/v1/gpu").json()
        for key in (
            "gpu_id", "model", "workload_mode", "temp_c", "power_w",
            "util_pct", "mem_used_mb", "mem_total_mb", "nvlink_bw_gbps",
            "ecc_corrected_total", "ecc_uncorrected_total", "active_faults",
        ):
            assert key in body


def test_ecc_uncorrected_is_one_shot_not_a_sustained_fault():
    with TestClient(app) as client:
        before = client.get("/api/v1/gpu").json()["ecc_uncorrected_total"]
        client.post("/api/v1/fault/ecc_uncorrected")
        body = client.get("/api/v1/gpu").json()
        assert body["ecc_uncorrected_total"] == before + 1
        assert "ecc_uncorrected" not in body["active_faults"]
