def test_app_exposes_snapshot_and_mode_routes(tmp_path):
    import yaml
    from pilot_ems.app import create_app

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"site": {"name": "试点"}, "devices": []}), encoding="utf-8")

    app = create_app(str(config_path), start_background=False)
    client = app.test_client()

    snapshot_response = client.get("/api/snapshot")
    mode_response = client.get("/api/mode")

    assert snapshot_response.status_code == 200
    assert snapshot_response.get_json()["site"]["name"] == "试点"
    assert mode_response.status_code == 200
    assert "mode" in mode_response.get_json()


def test_app_control_route_uses_control_layer(tmp_path):
    import yaml
    from pilot_ems.app import create_app

    config_path = tmp_path / "config.yaml"
    config = {
        "devices": [
            {
                "id": "pv_1",
                "type": "pv",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.11", "unit_id": 1},
                "controls": {"power_limit": {"addr": 41001, "type": "u16", "min": 0, "max": 1000}},
            }
        ]
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    calls = []

    def fake_writer(connection, field, value):
        calls.append((connection, field, value))
        return True, "ok"

    app = create_app(str(config_path), start_background=False, writers={"modbus": fake_writer})
    client = app.test_client()

    response = client.post(
        "/api/control",
        json={"device_id": "pv_1", "field": "power_limit", "value": 500},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert calls[0][2] == 500
