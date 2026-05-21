# 现场 Modbus 调试小工具

这组脚本用于第一次出差调试前准备。目标不是替代 EdgeFusion 正式运行时，而是在现场快速回答四个问题：

1. 设备链路通不通
2. unit id 对不对
3. 寄存器地址、类型、倍率、字序对不对
4. 控制寄存器能不能安全写入

脚本都在 `field_tools/` 目录下，每个文件都可以单独复制到现场电脑运行。只依赖 `pymodbus`。

## 0. 准备环境

```powershell
python --version
pip install pymodbus==3.5.4
```

Linux 工控机上也一样：

```bash
python3 --version
python3 -m pip install pymodbus==3.5.4
```

## 1. 先用 doctor 看链路

### Modbus TCP

```powershell
python field_modbus_doctor.py tcp --host 192.168.1.10 --port 502 --unit-range 1-10
```

### Modbus RTU

```powershell
python field_modbus_doctor.py rtu --serial-port COM3 --baudrate 9600 --unit-range 1-10
```

Linux 串口一般类似：

```bash
python3 field_modbus_doctor.py rtu --serial-port /dev/ttyUSB0 --baudrate 9600 --unit-range 1-10
```

如果没有任何 `OK`：

- TCP：检查 IP、端口、防火墙、设备是否在同网段
- RTU：检查串口号、波特率、校验位、停止位、485 A/B 是否接反
- unit id：扩大 `--unit-range 1-247`
- 地址：加 `--addr 1` 或换设备文档里的已知地址

## 2. 再用 read_table 批量读点

打开 `field_modbus_read_table.py`，修改顶部的 `FIELDS`：

```python
FIELDS = [
    {"name": "soc", "area": "holding", "addr": 32001, "type": "u16", "scale": 1, "unit": "%"},
    {"name": "power", "area": "holding", "addr": 32002, "type": "i32", "scale": 0.1, "unit": "kW"},
    {"name": "status", "area": "input", "addr": 30001, "type": "u16", "enum": {0: "offline", 1: "online"}},
]
```

然后运行：

```powershell
python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1
```

RTU：

```powershell
python field_modbus_read_table.py rtu --serial-port COM3 --baudrate 9600 --unit-id 1
```

如果怀疑地址基址不一致，使用：

```powershell
python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1 --probe-offsets
```

`--probe-offsets` 会尝试：

- `addr - 1`
- `addr`
- `addr + 1`
- `40001` 转 `0`
- `30001` 转 `0`

现场最常见问题就是厂家文档写 `40001`，程序实际要读 `0` 或 `1`。

## 3. 最后才做安全写入

默认不会真正写设备：

```powershell
python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000
```

确认无误后，才加 `--confirm-write`：

```powershell
python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000 --confirm-write
```

RTU：

```powershell
python field_modbus_safe_write.py rtu --serial-port COM3 --baudrate 9600 --unit-id 1 --addr 42001 --type u16 --value 3000 --confirm-write
```

多寄存器原始写入：

```powershell
python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 0x4000 --values 1,0x02,3000,0 --confirm-write
```

安全建议：

- 第一次写入只选厂家文档明确允许的安全控制点
- 写功率限值先写小值，不要直接写满功率
- 写之前记录现场设备状态
- 写后观察设备界面、指示灯、告警状态

## 4. 建议现场记录

每次成功读取或写入后，建议保存 JSON 报告：

```powershell
python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1 --json-report read_report.json
python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000 --confirm-write --json-report write_report.json
```

回到开发环境后，用这些信息整理正式 profile：

- 设备 IP / 串口参数
- unit id
- 每个字段的 area、addr、type、scale、unit
- status/mode 枚举值
- 控制点写入结果

## 5. 推荐现场顺序

```text
field_modbus_doctor.py
  -> 确认链路和 unit id

field_modbus_read_table.py
  -> 验证 2-5 个关键遥测字段

field_modbus_safe_write.py
  -> 验证 1 个安全控制字段

保存 JSON 报告
  -> 回来整理正式 profile
```
