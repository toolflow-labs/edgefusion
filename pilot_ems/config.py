import yaml


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _writable_fields(item):
    controls = item.get("controls") or {}
    return sorted(controls.keys())


def _entity_from_device(device):
    entity = dict(device)
    entity.pop("children", None)
    entity.setdefault("protocol", device.get("protocol", "modbus"))
    entity.setdefault("telemetry", {})
    entity.setdefault("controls", {})
    entity["capabilities"] = {
        "readable_fields": sorted(entity.get("telemetry", {}).keys()),
        "writable_fields": _writable_fields(entity),
    }
    return entity


def _entity_from_child(parent, child):
    entity = dict(child)
    entity["id"] = f"{parent['id']}.{child['id']}"
    entity["parent_id"] = parent["id"]
    entity["protocol"] = child.get("protocol", parent.get("protocol", "modbus"))
    entity["connection"] = dict(child.get("connection", parent.get("connection", {})))
    entity.setdefault("telemetry", {})
    entity.setdefault("controls", {})
    entity["capabilities"] = {
        "readable_fields": sorted(entity.get("telemetry", {}).keys()),
        "writable_fields": _writable_fields(entity),
    }
    return entity


def flatten_configured_entities(config):
    entities = []
    for device in config.get("devices", []) or []:
        if not device.get("id"):
            continue
        entities.append(_entity_from_device(device))
        for child in device.get("children", []) or []:
            if not child.get("id"):
                continue
            entities.append(_entity_from_child(device, child))
    return entities
