# 现场接入工具包

`field_tools` 只服务于第一次现场联调，不替代 EdgeFusion 正式运行时。

现场目标不是把后台系统做完整，而是快速形成结论：

1. 设备链路能不能通；
2. 关键遥测字段能不能读；
3. 控制接口能不能安全验证；
4. 能否留下可复盘的 JSON 报告和现场结论。

## 目录结构

```text
field_tools/
├── quick/
│   ├── field_modbus_check.py
│   ├── field_http_check.py
│   ├── field_mqtt_check.py
│   ├── field_points.yaml
│   └── field_record.md
├── advanced/
│   ├── field_modbus_doctor.py
│   ├── field_modbus_read_table.py
│   └── field_modbus_safe_write.py
└── protocol_notes/
    ├── http_device_check.md
    ├── mqtt_device_check.md
    ├── can_device_check.md
    └── ocpp_device_check.md
```

## 现场主路径

优先使用 `quick/`，只在 quick 工具无法定位问题时进入 `advanced/`。

```text
Modbus 本地接入  -> quick/field_modbus_check.py + quick/field_points.yaml
HTTP/云端接口    -> quick/field_http_check.py
MQTT/云端消息    -> quick/field_mqtt_check.py
现场结论沉淀     -> quick/field_record.md
```

`advanced/` 保留 Modbus 细分诊断脚本，用于 unit id 扫描、地址偏移排查、多寄存器写入等问题定位。

`protocol_notes/` 只放协议确认清单。CAN、OCPP、私有协议先按清单确认，不作为第一次联调主路径。

## 现场总原则

- 先笔记本调通，再迁移到融合终端硬件；
- 先连通，再读数，最后控制；
- 每类设备先验证 2-5 个关键字段，不抄完整点表；
- 控制默认 dry-run，必须显式 confirm 才下发；
- 每次成功读写都保存 JSON 报告；
- 回来后再把已验证事实整理进正式 profile 或本地后台。

## Modbus 快速用法

先编辑：

```text
quick/field_points.yaml
```

读取：

```powershell
python quick/field_modbus_check.py tcp --host 192.168.1.10 --unit-id 1 --points quick/field_points.yaml --read --json-report modbus_read_report.json
```

安全写入 dry-run：

```powershell
python quick/field_modbus_check.py tcp --host 192.168.1.10 --unit-id 1 --points quick/field_points.yaml --write power_limit=3000 --json-report modbus_write_dry_run.json
```

真正写入必须显式确认：

```powershell
python quick/field_modbus_check.py tcp --host 192.168.1.10 --unit-id 1 --points quick/field_points.yaml --write power_limit=3000 --confirm-write --json-report modbus_write_report.json
```

## HTTP 快速用法

读取：

```powershell
python quick/field_http_check.py --base-url http://192.168.1.20 --get /api/status --field power=$.power --field status=$.status --json-report http_read_report.json
```

控制 dry-run：

```powershell
python quick/field_http_check.py --base-url http://192.168.1.20 --post /api/control --body "{""cmd"":""set_power_limit"",""value"":3000}" --json-report http_write_dry_run.json
```

真正下发必须加：

```powershell
python quick/field_http_check.py --base-url http://192.168.1.20 --post /api/control --body "{""cmd"":""set_power_limit"",""value"":3000}" --confirm-write --json-report http_write_report.json
```

## MQTT 快速用法

订阅遥测：

```powershell
python quick/field_mqtt_check.py --host 192.168.1.30 --port 1883 --topic "device/+/telemetry" --count 3 --json-report mqtt_read_report.json
```

控制 dry-run：

```powershell
python quick/field_mqtt_check.py --host 192.168.1.30 --pub-topic "device/ess/1/control" --payload "{""cmd"":""set_power_limit"",""value"":3000}" --json-report mqtt_write_dry_run.json
```

真正 publish 必须加：

```powershell
python quick/field_mqtt_check.py --host 192.168.1.30 --pub-topic "device/ess/1/control" --payload "{""cmd"":""set_power_limit"",""value"":3000}" --confirm-publish --json-report mqtt_write_report.json
```

## 现场收口

每台设备最终使用 `quick/field_record.md` 收口，不要只留下零散命令和截图。