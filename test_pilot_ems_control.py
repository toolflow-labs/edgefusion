def test_write_control_rejects_out_of_range_value():
    from pilot_ems.control import write_control

    config = {
        "devices": [
            {
                "id": "storage_1",
                "type": "energy_storage",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.10", "unit_id": 1},
                "controls": {
                    "charge_power": {"addr": 42001, "type": "u16", "min": 0, "max": 50000}
                },
            }
        ]
    }
    calls = []

    def fake_writer(connection, field, value):
        calls.append((connection, field, value))
        return True, "ok"

    result = write_control(config, "storage_1", "charge_power", 60000, writers={"modbus": fake_writer})

    assert result["success"] is False
    assert "max" in result["message"]
    assert calls == []


def test_write_control_routes_child_entity_control():
    from pilot_ems.control import write_control

    config = {
        "devices": [
            {
                "id": "charger_1",
                "type": "charger",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.12", "unit_id": 1},
                "children": [
                    {
                        "id": "gun1",
                        "type": "charging_connector",
                        "controls": {
                            "power_limit": {"addr": 0x4000, "type": "u16", "min": 0, "max": 120}
                        },
                    }
                ],
            }
        ]
    }
    calls = []

    def fake_writer(connection, field, value):
        calls.append((connection, field, value))
        return True, "ok"

    result = write_control(config, "charger_1.gun1", "power_limit", 60, writers={"modbus": fake_writer})

    assert result["success"] is True
    assert calls[0][0]["host"] == "192.168.1.12"
    assert calls[0][1]["addr"] == 0x4000
    assert calls[0][2] == 60
