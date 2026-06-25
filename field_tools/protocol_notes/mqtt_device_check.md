# MQTT 设备最小确认清单

MQTT 的关键不是“能不能接线”，而是 broker、topic、payload 和设备连接方向。

## 1. 先确认 broker 在哪里

常见三种：

1. 设备内置 broker，我们连接设备
2. 我们提供本地 broker，设备主动连接
3. 厂家云 broker，双方都连厂家平台

记录：

```text
broker_host =
broker_port =
username =
password/token =
tls =
设备连接方向 =
```

如果是厂家云 broker，第一次试点要确认现场网络是否允许外网、账号是否可用、topic 权限是否开放。

## 2. 安装测试工具

推荐 Mosquitto 客户端：

```powershell
mosquitto_sub --help
mosquitto_pub --help
```

没有工具时，也可以让厂家现场导出报文样例。

## 3. 订阅遥测 topic

无认证：

```powershell
mosquitto_sub -h 192.168.1.30 -p 1883 -t "#" -v
```

带账号：

```powershell
mosquitto_sub -h 192.168.1.30 -p 1883 -u user -P password -t "#" -v
```

如果 `#` 没权限，需要厂家给明确 topic，例如：

```powershell
mosquitto_sub -h 192.168.1.30 -p 1883 -t "device/+/telemetry" -v
```

## 4. 保存样例 payload

记录至少 3 条连续上报，确认周期和字段是否稳定：

```text
topic =
payload =
qos =
retain =
上报周期 =
```

JSON 示例：

```json
{
  "power": 12345,
  "status": "normal",
  "soc": 78
}
```

非 JSON 要保存原文，不要现场硬猜。

## 5. 标出字段路径

```text
power  -> topic=device/ess/1/telemetry, path=$.power
soc    -> topic=device/ess/1/telemetry, path=$.soc
status -> topic=device/ess/1/telemetry, path=$.status
```

同时确认：

- 单位
- 倍率
- 状态码
- 离线时是否停止上报
- retained 消息是否可能是旧值

## 6. 控制 topic

先确认设备是否支持控制 topic，以及是否有 ack。

发布示例：

```powershell
mosquitto_pub -h 192.168.1.30 -p 1883 -t "device/ess/1/control" -m "{\"cmd\":\"set_power_limit\",\"value\":3000}"
```

记录：

- control topic
- payload 格式
- qos
- 是否需要 retained=false
- ack topic
- 控制失败时响应
- 是否能读回控制结果

## 7. 最小通过标准

- broker 地址和认证方式明确
- 能订阅到遥测 topic
- payload 格式和字段路径明确
- 上报周期明确
- 控制 topic 是否开放明确
