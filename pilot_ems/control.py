from datetime import datetime

from .config import flatten_configured_entities
from . import io_http, io_modbus


def default_writers():
    return {
        "modbus": io_modbus.write_field,
        "http": io_http.write_field,
    }


def find_entity(config, device_id):
    for entity in flatten_configured_entities(config):
        if entity["id"] == device_id:
            return entity
    return None


def write_control(config, device_id, field_name, value, writers=None):
    writers = writers or default_writers()
    entity = find_entity(config, device_id)
    if not entity:
        return {"success": False, "message": f"device not found: {device_id}"}

    field = (entity.get("controls") or {}).get(field_name)
    if not field:
        return {"success": False, "message": f"control not found: {field_name}"}

    number = float(value)
    if "min" in field and number < float(field["min"]):
        return {"success": False, "message": f"value below min {field['min']}"}
    if "max" in field and number > float(field["max"]):
        return {"success": False, "message": f"value above max {field['max']}"}

    protocol = str(entity.get("protocol", "modbus")).lower()
    writer = writers.get(protocol)
    if not writer:
        return {"success": False, "message": f"unsupported protocol: {protocol}"}

    success, message = writer(entity.get("connection", {}), field, number)
    return {
        "success": bool(success),
        "message": message,
        "device_id": device_id,
        "field": field_name,
        "value": number,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
