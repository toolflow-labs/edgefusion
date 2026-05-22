def test_extract_json_path_reads_nested_values():
    from pilot_ems.io_http import extract_json_path

    payload = {"battery": {"soc": 78}, "power": 1234}

    assert extract_json_path(payload, "$.battery.soc") == 78
    assert extract_json_path(payload, "$.power") == 1234


def test_render_body_replaces_value_placeholder():
    from pilot_ems.io_http import render_body

    body = render_body({"cmd": "set_power_limit", "value": "{{ value }}"}, 3000)

    assert body == b'{"cmd": "set_power_limit", "value": 3000}'
