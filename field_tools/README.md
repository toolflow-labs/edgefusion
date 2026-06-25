# 现场接入工具包（精简版）

这个目录用于现场出差联调，只回答三件事：

1. 能不能连上设备
2. 能不能读到关键字段
3. 能不能下发控制并留下证据

不要在现场把它当成完整平台。

## 主路径（推荐）

### Modbus
- field_modbus_doctor.py
- field_modbus_read_table.py
- field_modbus_safe_write.py

### HTTP
- field_http_check.py

### MQTT
- field_mqtt_check.py

### 结果
- field_report_template.md

## 原则

- 先连通，再读数，最后控制
- 只验证 2-5 个关键字段
- 控制默认 dry-run
- 所有操作必须有 JSON 证据

## 不做的事

- 不做完整框架
- 不做复杂抽象
- 不做多设备平台化
