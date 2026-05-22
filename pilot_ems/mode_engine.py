from datetime import datetime


def _parse_time(text):
    if not text:
        return datetime.now()
    return datetime.fromisoformat(text)


def _as_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _supports(snapshot, *fields):
    writable = snapshot.get("capabilities", {}).get("writable_fields")
    if not isinstance(writable, list):
        return True
    return all(field in writable for field in fields)


def _is_online(snapshot):
    status = str(snapshot.get("data", {}).get("status", "online")).lower()
    return status not in ("offline", "fault", "error")


def build_site_state(snapshots, config=None):
    config = config or {}
    latest = {}
    latest_time = datetime.min
    for snapshot in snapshots:
        device_id = snapshot.get("device_id")
        if not device_id:
            continue
        timestamp = _parse_time(snapshot.get("timestamp"))
        if device_id not in latest or _parse_time(latest[device_id].get("timestamp")) <= timestamp:
            latest[device_id] = snapshot
        if timestamp > latest_time:
            latest_time = timestamp

    if latest_time == datetime.min:
        latest_time = datetime.now()

    grid_power = None
    pv_power = 0.0
    issues = []
    max_age = int(config.get("max_data_age_seconds", 30))

    for snapshot in latest.values():
        timestamp = _parse_time(snapshot.get("timestamp"))
        if (latest_time - timestamp).total_seconds() > max_age:
            issues.append(f"stale:{snapshot.get('device_id')}")
        data = snapshot.get("data", {})
        if snapshot.get("device_type") in ("grid", "grid_meter") and data.get("power") is not None:
            grid_power = float(data["power"])
        if snapshot.get("device_type") == "pv" and data.get("power") is not None:
            pv_power += float(data["power"])

    if grid_power is None:
        issues.append("missing_grid_power")

    return {
        "timestamp": latest_time,
        "grid_power_w": grid_power,
        "pv_power_w": pv_power,
        "trusted": not issues,
        "trust_issues": issues,
        "manual_override": bool(config.get("manual_override", False)),
        "snapshots": latest,
    }


def arbitrate_mode(state, config=None):
    config = config or {}
    if state.get("manual_override"):
        return {"mode": "manual_override", "reason": "manual_override_enabled"}
    if not state.get("trusted"):
        return {"mode": "safe_hold", "reason": "untrusted_site_state"}
    if not bool(config.get("export_protect_enabled", True)):
        return {"mode": "business_normal", "reason": "export_protect_disabled"}

    export_limit = float(config.get("export_limit_w", 0))
    enter_ratio = float(config.get("export_enter_ratio", 1.0))
    threshold = -export_limit * enter_ratio
    if state.get("grid_power_w") is not None and state["grid_power_w"] <= threshold:
        return {"mode": "export_protect", "reason": "export_limit_exceeded"}
    return {"mode": "business_normal", "reason": "normal_operation"}


def _snapshots_by_type(state, device_types):
    if isinstance(device_types, str):
        device_types = (device_types,)
    return [
        snapshot
        for snapshot in state.get("snapshots", {}).values()
        if snapshot.get("device_type") in device_types
    ]


def plan_export_protect(state, config=None):
    config = config or {}
    export_limit = int(config.get("export_limit_w", 0))
    storage_soc_limit = float(config.get("storage_soc_soft_limit", 95))
    gap = max(0, int(round(-(state.get("grid_power_w") or 0) - export_limit)))
    remaining = gap
    actions = []

    for snapshot in _snapshots_by_type(state, "energy_storage"):
        if remaining <= 0 or not _is_online(snapshot) or not _supports(snapshot, "mode", "charge_power"):
            continue
        data = snapshot.get("data", {})
        if float(data.get("soc", 0) or 0) >= storage_soc_limit:
            continue
        charge = min(remaining, max(0, _as_int(data.get("max_charge_power"))))
        if charge <= 0:
            continue
        actions.append({"device_id": snapshot["device_id"], "action": "set_charge_power", "value_w": charge})
        remaining -= charge

    for snapshot in _snapshots_by_type(state, ("charging_connector", "charger")):
        if remaining <= 0 or not _is_online(snapshot) or not _supports(snapshot, "power_limit"):
            continue
        data = snapshot.get("data", {})
        power = _as_int(data.get("power"))
        max_power = _as_int(data.get("max_power"), power)
        headroom = max(0, max_power - power)
        increase = min(remaining, headroom)
        if power <= 0 or increase <= 0:
            continue
        actions.append({"device_id": snapshot["device_id"], "action": "set_power_limit", "value_w": power + increase})
        remaining -= increase

    for snapshot in _snapshots_by_type(state, "pv"):
        if remaining <= 0 or not _is_online(snapshot) or not _supports(snapshot, "power_limit"):
            continue
        data = snapshot.get("data", {})
        current_limit = _as_int(data.get("power_limit"), _as_int(data.get("power")))
        min_limit = _as_int(data.get("min_power_limit"))
        curtail = min(remaining, max(0, current_limit - min_limit))
        if curtail <= 0:
            continue
        actions.append({"device_id": snapshot["device_id"], "action": "set_power_limit", "value_w": current_limit - curtail})
        remaining -= curtail

    return {"mode": "export_protect", "actions": actions, "remaining_gap_w": remaining}
