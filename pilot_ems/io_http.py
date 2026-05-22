import json
from urllib import request


def join_url(base_url, path):
    return str(base_url).rstrip("/") + "/" + str(path or "").lstrip("/")


def extract_json_path(payload, path):
    if not path or path == "$":
        return payload
    if not str(path).startswith("$."):
        raise ValueError(f"only simple $.a.b paths are supported: {path}")

    value = payload
    for part in str(path)[2:].split("."):
        value = value[part]
    return value


def apply_scale(value, field):
    if not isinstance(value, (int, float)):
        return value
    result = value * float(field.get("scale", 1) or 1) + float(field.get("offset", 0) or 0)
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


def render_body(body, value):
    if body is None:
        body = {"value": "{{ value }}"}
    if isinstance(body, str):
        return body.replace("{{ value }}", str(value)).encode("utf-8")
    rendered = {}
    for key, item in body.items():
        rendered[key] = value if item == "{{ value }}" else item
    return json.dumps(rendered).encode("utf-8")


def read_fields(connection, telemetry):
    values = {}
    errors = []
    for name, field in telemetry.items():
        try:
            url = join_url(connection.get("base_url"), field.get("path", "/"))
            headers = dict(connection.get("headers", {}))
            req = request.Request(url, method=str(field.get("method", "GET")).upper(), headers=headers)
            with request.urlopen(req, timeout=float(connection.get("timeout", 3))) as response:
                payload = json.loads(response.read().decode("utf-8"))
            values[name] = apply_scale(extract_json_path(payload, field.get("json_path", "$")), field)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return values, errors


def write_field(connection, field, value):
    try:
        url = join_url(connection.get("base_url"), field.get("path", "/"))
        headers = {"Content-Type": "application/json"}
        headers.update(connection.get("headers", {}))
        req = request.Request(
            url,
            data=render_body(field.get("body"), value),
            method=str(field.get("method", "POST")).upper(),
            headers=headers,
        )
        with request.urlopen(req, timeout=float(connection.get("timeout", 3))) as response:
            response.read()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
