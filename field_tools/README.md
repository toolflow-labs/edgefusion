# 现场接入工具包

`field_tools` 只服务于第一次现场联调，不替代 EdgeFusion 正式运行时。

现场目标不是把后台系统做完整，而是快速形成结论：

1. 设备链路能不能通；
2. 关键遥测字段能不能读；
3. 控制接口能不能安全验证；
4. 能否留下可复盘的 JSON 报告和现场结论。

## 现场主路径

优先按设备实际开放的接口选择一条路径，不要同时铺开所有协议。

```text
Modbus 本地接入  -> field_modbus_doctor.py -> field_modbus_read_table.py -> field_modbus_safe_write.py
HTTP/云端接口    -> field_http_check.py
MQTT/云端消息    -> field_mqtt_check.py
现场结论沉淀     -> field_report_template.md
```

CAN、OCPP、私有协议先按清单确认，不作为第一次联调主路径。

## 0. 现场总原则

- 先笔记本调通，再迁移到融合终端硬件；
- 先连通，再读数，最后控制；
- 每类设备先验证 2-5 个关键字段，不抄完整点表；
- 控制默认 dry-run，必须显式 confirm 才下发；
- 每次成功读写都保存 JSON 报告；
- 回来后再把已验证事实整理进正式 profile 或本地后台。

## 1. Modbus 路径

### 1.1 连通性和 unit id

TCP：

```powershell
python field_modbus_doctor.py tcp --host 192.168.1.10 --port 502 --unit-range 1-10
```

RTU：

```powershell
python field_modbus_doctor.py rtu --serial-port COM3 --baudrate 9600 --unit-range 1-10
```

如果没有任何 `OK`，优先检查：

- TCP：IP、端口、防火墙、网段；
- RTU：串口号、波特率、校验位、停止位、485 A/B；
- unit id：扩大到 `--unit-range 1-247`；
- 地址：换厂家文档里明确可读的寄存器。

### 1.2 读取关键字段

打开 `field_modbus_read_table.py`，只改顶部 `FIELDS`，先填 2-5 个字段：

```python
FIELDS = [
    {"name": "power", "area": "holding", "addr": 32002, "type": "i32", "scale": 0.1, "unit": "kW"},
    {"name": "status", "area": "input", "addr": 30001, "type": "u16", "enum": {0: "offline", 1: "online"}},
]
```

运行：

```powershell
python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1 --json-report read_report.json
```

如果怀疑厂家文档地址是 30001/40001 口径，增加：

```powershell
python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1 --probe-offsets --json-report read_report.json
```

### 1.3 安全写入

默认 dry-run，不真正写设备：

```powershell
python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000 --json-report write_dry_run.json
```

确认厂家允许、现场状态安全后，才加：

```powershell
python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000 --confirm-write --json-report write_report.json
```

## 2. HTTP 路径

HTTP 路径用于厂家网关、本地 Web API 或云端接口。目标是确认 URL、鉴权、响应格式、字段路径和控制接口。

### 2.1 读取状态接口

```powershell
python field_http_check.py ^
  --base-url http://192.168.1.20 ^
  --get /api/status ^
  --field power=$.power ^
  --field status=$.status ^
  --json-report http_read_report.json
```

Bearer Token：

```powershell
python field_http_check.py ^
  --base-url https://vendor.example.com ^
  --get /api/status ^
  --auth bearer:TOKEN ^
  --field power=$.data.power ^
  --json-report http_read_report.json
```

Basic 认证：

```powershell
python field_http_check.py --base-url http://192.168.1.20 --get /api/status --auth basic:user:password
```

### 2.2 控制接口 dry-run

```powershell
python field_http_check.py ^
  --base-url http://192.168.1.20 ^
  --post /api/control ^
  --body "{""cmd"":""set_power_limit"",""value"":3000}" ^
  --json-report http_write_dry_run.json
```

真正下发必须加：

```powershell
python field_http_check.py ^
  --base-url http://192.168.1.20 ^
  --post /api/control ^
  --body "{""cmd"":""set_power_limit"",""value"":3000}" ^
  --confirm-write ^
  --json-report http_write_report.json
```

## 3. MQTT 路径

MQTT 路径用于厂家云 broker、本地 broker 或设备主动上报场景。目标是确认 broker、认证、topic、payload、上报周期和控制 topic。

先安装依赖：

```powershell
pip install paho-mqtt==1.6.1
```

### 3.1 订阅遥测

```powershell
python field_mqtt_check.py ^
  --host 192.168.1.30 ^
  --port 1883 ^
  --topic "device/+/telemetry" ^
  --count 3 ^
  --json-report mqtt_read_report.json
```

带账号：

```powershell
python field_mqtt_check.py ^
  --host mqtt.vendor.example.com ^
  --port 8883 ^
  --tls ^
  --username user ^
  --password password ^
  --topic "device/+/telemetry" ^
  --count 3 ^
  --json-report mqtt_read_report.json
```

### 3.2 控制 publish dry-run

```powershell
python field_mqtt_check.py ^
  --host 192.168.1.30 ^
  --pub-topic "device/ess/1/control" ^
  --payload "{""cmd"":""set_power_limit"",""value"":3000}" ^
  --json-report mqtt_write_dry_run.json
```

真正 publish 必须加：

```powershell
python field_mqtt_check.py ^
  --host 192.168.1.30 ^
  --pub-topic "device/ess/1/control" ^
  --payload "{""cmd"":""set_power_limit"",""value"":3000}" ^
  --confirm-publish ^
  --json-report mqtt_write_report.json
```

如果厂家提供 ack topic，同时订阅：

```powershell
python field_mqtt_check.py ^
  --host 192.168.1.30 ^
  --topic "device/ess/1/telemetry" ^
  --ack-topic "device/ess/1/ack" ^
  --pub-topic "device/ess/1/control" ^
  --payload "{""cmd"":""set_power_limit"",""value"":3000}" ^
  --confirm-publish ^
  --json-report mqtt_control_report.json
```

## 4. 现场结论

每台设备最终只需要沉淀这些结果：

```text
设备类型：总表 / 光伏 / 储能 / 充电桩
接入方式：Modbus TCP / Modbus RTU / HTTP / MQTT / 其他
遥测是否可接入：是 / 否
控制是否可接入：是 / 否 / 厂家暂不开放 / 仅云端开放
关键证据：read_report.json / write_report.json / 现场照片或视频
后续动作：整理 profile / 补云端适配 / 暂不接入
```

使用 `field_report_template.md` 收口，不要只留下零散命令。