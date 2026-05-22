# Pilot EMS Runtime Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate minimal trial runtime that can explicitly configure, collect, display, and safely control pilot-site grid meter, PV, storage, and charger devices without carrying EdgeFusion's profile/catalog/autodiscovery stack.

**Architecture:** Create a new `pilot_ems/` package beside `edgefusion/`. It uses explicit YAML configuration, thin Modbus TCP/RTU and optional HTTP/JSON IO, a periodic collector, in-memory latest state, a simple Flask dashboard/API, and a copied/simplified mode engine based on EdgeFusion's existing `site_state`, `mode_engine`, and `export_protect` logic.

**Tech Stack:** Python, Flask, PyYAML, pymodbus, SQLite via stdlib `sqlite3` only if persistence is enabled. Tests use pytest and fake IO functions; no dependency on EdgeFusion runtime internals.

---

## Boundaries

This runtime is for the first pilot project. It intentionally does not implement:

- model catalog
- profile registry
- automatic discovery
- candidate devices
- device onboarding UI
- vendor profiles
- adapter normalization
- complex capability inference
- broad protocol plugin framework

It does implement:

- explicit device and field config
- Modbus TCP/RTU telemetry and writes
- optional HTTP/JSON telemetry and writes
- periodic collection
- latest snapshot API
- simple dashboard
- manual white-list controls with min/max validation
- monitor-only mode decision and optional manual execution of planned actions

---

## File Structure

Create:

- `pilot_ems/__init__.py`: package marker.
- `pilot_ems/config.example.yaml`: field-editable sample config for grid meter, PV, storage, charger, and child connector entities.
- `pilot_ems/io_modbus.py`: plain Modbus TCP/RTU read/write helpers copied in style from `field_tools`, not EdgeFusion abstractions.
- `pilot_ems/io_http.py`: minimal HTTP/JSON GET/POST helpers using stdlib `urllib`.
- `pilot_ems/collector.py`: collection loop and one-shot collection over configured devices and child entities.
- `pilot_ems/state.py`: latest snapshot storage and site snapshot helpers.
- `pilot_ems/control.py`: white-list control lookup, min/max validation, write dispatch, operation log entries.
- `pilot_ems/mode_engine.py`: simplified copy of `build_site_state`, `arbitrate_mode`, and `plan_export_protect`.
- `pilot_ems/app.py`: Flask app, API routes, startup entrypoint.
- `pilot_ems/templates/index.html`: single-page dashboard.
- `pilot_ems/README.md`: field usage, config rules, startup, control API, and relationship to `field_tools`.
- `test_pilot_ems_*.py`: focused tests for config expansion, IO codec, collection, control validation, and mode decisions.

Do not modify EdgeFusion runtime files in this phase.

---

## Chunk 1: Config Shape And Snapshot Model

### Task 1: Define explicit config and flattening behavior

**Files:**
- Create: `test_pilot_ems_config.py`
- Create: `pilot_ems/__init__.py`
- Create: `pilot_ems/config.py`
- Create: `pilot_ems/config.example.yaml`

- [ ] **Step 1: Write failing tests for physical devices and child entities**

Test that a physical charger with `children` produces one parent item and child snapshot ids like `charger_1.gun1`, without requiring the field technician to configure the gun as a separate physical device.

Expected test shape:

```python
def test_flatten_devices_keeps_physical_device_and_children():
    from pilot_ems.config import flatten_configured_entities

    config = {
        "devices": [
            {
                "id": "charger_1",
                "type": "charger",
                "connection": {"transport": "tcp", "host": "192.168.1.12", "unit_id": 1},
                "children": [
                    {"id": "gun1", "type": "charging_connector", "telemetry": {"power": {"addr": 0x200E}}}
                ],
            }
        ]
    }

    entities = flatten_configured_entities(config)

    assert [item["id"] for item in entities] == ["charger_1", "charger_1.gun1"]
    assert entities[1]["parent_id"] == "charger_1"
    assert entities[1]["connection"]["host"] == "192.168.1.12"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_config.py -q
```

Expected: `ModuleNotFoundError: No module named 'pilot_ems'`.

- [ ] **Step 3: Implement minimal config helpers**

Implement:

```python
def load_config(path):
    ...

def flatten_configured_entities(config):
    ...
```

Rules:

- Parent device keeps its own `telemetry` and `controls`.
- Child entity inherits parent `protocol` and `connection`.
- Child `id` becomes `parent.child`.
- Child keeps `parent_id`.
- No model/profile/vendor logic.

- [ ] **Step 4: Add `config.example.yaml`**

Include examples for:

- `grid_meter`
- `pv`
- `energy_storage`
- `charger` with `children`
- one optional `http` device

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_config.py -q
```

Expected: PASS.

---

## Chunk 2: IO Layer

### Task 2: Implement Modbus codec and thin IO

**Files:**
- Create: `test_pilot_ems_modbus.py`
- Create: `pilot_ems/io_modbus.py`

- [ ] **Step 1: Write failing tests for codec**

Cover:

- `u16`
- `i16`
- `u32`
- `i32`
- `f32`
- `scale`
- `word_order=little`

Use real functions, no pymodbus client required for codec tests.

- [ ] **Step 2: Verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_modbus.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement codec in plain script style**

Use the style from `field_tools/field_modbus_read_table.py`:

- no complex type annotations
- clear `if area == "holding"` branches
- simple comments for field technicians

- [ ] **Step 4: Implement `read_fields(connection, telemetry)` and `write_field(connection, field, value)`**

Support:

- `area: holding`
- `area: input`
- `area: coil`
- `area: discrete`
- writes only to `holding` for first version

Return `(values, errors)` for reads and `(success, message)` for writes.

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_modbus.py -q
```

Expected: PASS.

### Task 3: Implement minimal HTTP/JSON IO

**Files:**
- Create: `test_pilot_ems_http.py`
- Create: `pilot_ems/io_http.py`

- [ ] **Step 1: Write failing tests for JSON path extraction**

Cover simple `$.power` and `$.battery.soc`.

- [ ] **Step 2: Implement stdlib HTTP helpers**

Implement:

- `extract_json_path(data, path)`
- `read_fields(connection, telemetry)`
- `write_field(connection, field, value)`

Do not add requests dependency.

- [ ] **Step 3: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_http.py -q
```

Expected: PASS.

---

## Chunk 3: Collector, Latest State, And Control

### Task 4: Implement one-shot collection

**Files:**
- Create: `test_pilot_ems_collector.py`
- Create: `pilot_ems/collector.py`
- Create: `pilot_ems/state.py`

- [ ] **Step 1: Write failing collection test**

Use fake readers:

```python
def fake_modbus_reader(connection, fields):
    return {"power": 1234}, []
```

Assert snapshots look like:

```python
{
  "device_id": "meter_1",
  "device_type": "grid_meter",
  "timestamp": "...",
  "data": {"power": 1234},
  "capabilities": {"writable_fields": []},
  "errors": [],
}
```

- [ ] **Step 2: Implement collection**

Rules:

- Iterate `flatten_configured_entities(config)`.
- Dispatch by `protocol`.
- Snapshot includes `parent_id` when present.
- `capabilities.writable_fields` is simply `controls.keys()`.

- [ ] **Step 3: Implement latest state**

`LatestState` should store latest snapshots by device id and return:

- all latest snapshots
- one device latest snapshot
- site summary for dashboard

- [ ] **Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_collector.py -q
```

Expected: PASS.

### Task 5: Implement safe control dispatch

**Files:**
- Create: `test_pilot_ems_control.py`
- Create: `pilot_ems/control.py`

- [ ] **Step 1: Write failing tests**

Cover:

- unknown device rejected
- unknown field rejected
- value below min rejected
- value above max rejected
- valid write calls correct writer
- child control `charger_1.gun1.power_limit` works

- [ ] **Step 2: Implement control lookup and validation**

Rules:

- Control must exist in explicit config.
- `min/max` checked before write.
- No auto-generated controls.
- Writes dispatch by parent/device protocol.
- Return a dict with `success`, `message`, `timestamp`.

- [ ] **Step 3: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_control.py -q
```

Expected: PASS.

---

## Chunk 4: Mode Engine

### Task 6: Copy and simplify mode logic

**Files:**
- Create: `test_pilot_ems_mode_engine.py`
- Create: `pilot_ems/mode_engine.py`

- [ ] **Step 1: Write tests from existing mode behavior**

Adapt from `test_mode_engine.py`:

- missing grid power -> untrusted/safe hold
- grid export beyond limit -> export protect
- export disabled -> business normal
- export plan uses storage, active charging connectors, then PV curtailment

- [ ] **Step 2: Implement minimal mode engine**

Copy concepts, not the whole strategy wrapper:

- `build_site_state(snapshots, config)`
- `arbitrate_mode(state, config)`
- `plan_export_protect(state, config)`

Do not implement:

- dashboard mode config metadata
- simulated/real filtering
- candidate devices

- [ ] **Step 3: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_mode_engine.py -q
```

Expected: PASS.

---

## Chunk 5: Flask App And Dashboard

### Task 7: Implement API and dashboard

**Files:**
- Create: `test_pilot_ems_app.py`
- Create: `pilot_ems/app.py`
- Create: `pilot_ems/templates/index.html`
- Create: `pilot_ems/README.md`

- [ ] **Step 1: Write failing Flask app tests**

Use Flask test client:

- `GET /api/snapshot`
- `POST /api/collect`
- `GET /api/mode`
- `POST /api/control`

- [ ] **Step 2: Implement app factory**

Implement:

```python
def create_app(config_path):
    ...
```

Keep background collection optional for tests.

- [ ] **Step 3: Implement single page dashboard**

Display:

- grid meter power
- PV power
- storage SOC/power/mode
- charger child status/power
- latest errors
- current mode
- recent control results

No onboarding UI.

- [ ] **Step 4: Add README**

Include:

- install deps
- copy config
- run command
- how to use with `field_tools`
- control API examples
- first pilot success criteria

- [ ] **Step 5: Run app tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_app.py -q
```

Expected: PASS.

---

## Chunk 6: Optional Persistence And Final Verification

### Task 8: Add simple SQLite persistence only if needed

**Files:**
- Create: `test_pilot_ems_database.py`
- Create: `pilot_ems/database.py`

- [ ] **Step 1: Confirm persistence is still needed**

If the first pilot only needs dashboard latest values and logs, skip this task.

- [ ] **Step 2: Implement one table**

Suggested table:

```sql
CREATE TABLE readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  device_id TEXT NOT NULL,
  device_type TEXT NOT NULL,
  data_json TEXT NOT NULL,
  errors_json TEXT NOT NULL
)
```

- [ ] **Step 3: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_database.py -q
```

Expected: PASS.

### Task 9: Full verification

**Files:**
- Modify as needed based on test results.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_pilot_ems_config.py test_pilot_ems_modbus.py test_pilot_ems_http.py test_pilot_ems_collector.py test_pilot_ems_control.py test_pilot_ems_mode_engine.py test_pilot_ems_app.py -q
```

Expected: all pass.

- [ ] **Step 2: Run existing field tool tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test_field_modbus_tools.py test_modbus_probe.py -q
```

Expected: all pass.

- [ ] **Step 3: Smoke test command help**

Run:

```powershell
.\.venv\Scripts\python.exe -m pilot_ems.app --help
```

Expected: help text prints. If local `.venv` points to a missing base Python, recreate `.venv` before treating this as app failure.

---

## First Pilot Success Criteria

The first version is successful if it can:

1. Load explicit config for one grid meter and at least one controllable object.
2. Read stable latest values into snapshots.
3. Show latest values and errors in dashboard.
4. Reject unsafe control values outside configured bounds.
5. Execute one manually triggered safe control.
6. Show mode decision based on latest snapshots.
7. Avoid any dependency on EdgeFusion profile/catalog/autodiscovery code.

