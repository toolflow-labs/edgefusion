def test_collect_once_reads_parent_and_child_entities():
    from pilot_ems.collector import collect_once

    config = {
        "devices": [
            {
                "id": "meter_1",
                "type": "grid_meter",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.10", "unit_id": 1},
                "telemetry": {"power": {"addr": 1, "type": "i32"}},
            },
            {
                "id": "charger_1",
                "type": "charger",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.12", "unit_id": 1},
                "children": [
                    {
                        "id": "gun1",
                        "type": "charging_connector",
                        "telemetry": {
                            "status": {"addr": 0x2000, "type": "u16"},
                            "power": {"addr": 0x200E, "type": "u32"},
                        },
                        "controls": {"power_limit": {"addr": 0x4000, "type": "u16"}},
                    }
                ],
            },
        ]
    }

    def fake_modbus_reader(connection, telemetry):
        values = {}
        for name in telemetry:
            values[name] = 1 if name == "status" else 12.5
        return values, []

    snapshots = collect_once(config, readers={"modbus": fake_modbus_reader})

    assert [item["device_id"] for item in snapshots] == ["meter_1", "charger_1", "charger_1.gun1"]
    assert snapshots[0]["data"]["power"] == 12.5
    assert snapshots[2]["parent_id"] == "charger_1"
    assert snapshots[2]["capabilities"]["writable_fields"] == ["power_limit"]


def test_collector_loop_collects_into_latest_state():
    from pilot_ems.collector import CollectorLoop
    from pilot_ems.state import LatestState

    config = {
        "devices": [
            {
                "id": "meter_1",
                "type": "grid_meter",
                "protocol": "modbus",
                "connection": {"transport": "tcp", "host": "192.168.1.10", "unit_id": 1},
                "telemetry": {"power": {"addr": 1, "type": "i32"}},
            }
        ]
    }

    def fake_modbus_reader(connection, telemetry):
        return {"power": 1234}, []

    latest = LatestState({"name": "试点"})
    loop = CollectorLoop(config, latest, readers={"modbus": fake_modbus_reader})

    snapshots = loop.collect()

    assert snapshots[0]["data"]["power"] == 1234
    assert latest.snapshot()["devices"][0]["device_id"] == "meter_1"


def test_collector_loop_start_and_stop_manage_running_flag():
    from pilot_ems.collector import CollectorLoop
    from pilot_ems.state import LatestState

    loop = CollectorLoop({"collect_interval": 60, "devices": []}, LatestState())

    loop.start()
    assert loop.running is True
    assert loop.thread is not None

    loop.stop()
    assert loop.running is False
