from datetime import datetime


def snapshot(device_id, device_type, data):
    return {
        "device_id": device_id,
        "device_type": device_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "capabilities": {"writable_fields": list(data.get("_writes", []))},
    }


def test_missing_grid_power_enters_safe_hold():
    from pilot_ems.mode_engine import arbitrate_mode, build_site_state

    state = build_site_state([snapshot("pv_1", "pv", {"power": 5000})], {})
    decision = arbitrate_mode(state, {"export_limit_w": 5000})

    assert state["trusted"] is False
    assert decision["mode"] == "safe_hold"


def test_export_limit_exceeded_enters_export_protect():
    from pilot_ems.mode_engine import arbitrate_mode, build_site_state

    state = build_site_state([snapshot("meter_1", "grid_meter", {"power": -6500})], {})
    decision = arbitrate_mode(state, {"export_limit_w": 5000})

    assert decision["mode"] == "export_protect"


def test_export_plan_uses_storage_then_charger_then_pv():
    from pilot_ems.mode_engine import build_site_state, plan_export_protect

    snapshots = [
        snapshot("meter_1", "grid_meter", {"power": -12000}),
        snapshot(
            "storage_1",
            "energy_storage",
            {"soc": 40, "max_charge_power": 3000, "_writes": ["mode", "charge_power"]},
        ),
        snapshot(
            "charger_1.gun1",
            "charging_connector",
            {"status": "charging", "power": 2000, "max_power": 3500, "_writes": ["power_limit"]},
        ),
        snapshot(
            "pv_1",
            "pv",
            {"power": 8000, "power_limit": 8000, "min_power_limit": 0, "_writes": ["power_limit"]},
        ),
    ]

    state = build_site_state(snapshots, {})
    plan = plan_export_protect(state, {"export_limit_w": 5000})

    assert [action["device_id"] for action in plan["actions"]] == [
        "storage_1",
        "charger_1.gun1",
        "pv_1",
    ]
    assert plan["remaining_gap_w"] == 0
