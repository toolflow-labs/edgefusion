def test_flatten_devices_keeps_physical_device_and_children():
    from pilot_ems.config import flatten_configured_entities

    config = {
        "devices": [
            {
                "id": "charger_1",
                "type": "charger",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.12", "unit_id": 1},
                "telemetry": {"status": {"addr": 0x1000, "type": "u16"}},
                "children": [
                    {
                        "id": "gun1",
                        "type": "charging_connector",
                        "telemetry": {"power": {"addr": 0x200E, "type": "u32"}},
                    }
                ],
            }
        ]
    }

    entities = flatten_configured_entities(config)

    assert [item["id"] for item in entities] == ["charger_1", "charger_1.gun1"]
    assert entities[1]["parent_id"] == "charger_1"
    assert entities[1]["protocol"] == "modbus"
    assert entities[1]["connection"]["host"] == "192.168.1.12"


def test_flatten_devices_exposes_writable_fields_from_controls():
    from pilot_ems.config import flatten_configured_entities

    config = {
        "devices": [
            {
                "id": "storage_1",
                "type": "energy_storage",
                "connection": {"transport": "tcp", "host": "192.168.1.10", "unit_id": 1},
                "controls": {
                    "charge_power": {"addr": 42001, "type": "u16", "min": 0, "max": 50000}
                },
            }
        ]
    }

    entity = flatten_configured_entities(config)[0]

    assert entity["capabilities"]["writable_fields"] == ["charge_power"]
