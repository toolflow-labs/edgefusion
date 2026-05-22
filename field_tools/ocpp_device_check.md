# OCPP 充电桩最小确认清单

OCPP 是会话协议，不是像 Modbus 那样主动读寄存器。第一次试点要先确认桩能不能连接到我们的 Central System。

## 1. 先确认版本和连接方式

记录：

```text
OCPP 版本 = 1.6J / 2.0.1 / 其他
WebSocket URL =
桩编号 / chargeBoxId =
是否 TLS =
认证方式 =
厂家配置入口 =
```

常见 URL：

```text
ws://server:9000/ocpp/{chargeBoxId}
wss://server:9000/ocpp/{chargeBoxId}
```

## 2. 现场网络要求

确认：

- 充电桩能访问我们的服务器 IP 和端口
- 防火墙放行 WebSocket 端口
- 如果走公网或 4G，服务器地址是否可达
- TLS 证书是否被桩信任

## 3. 最小会话流程

桩连上后至少要看到：

```text
BootNotification
Heartbeat
StatusNotification
MeterValues
```

记录每类消息样例：

```text
BootNotification =
Heartbeat =
StatusNotification =
MeterValues =
```

## 4. 业务字段确认

从 OCPP 消息里确认：

- 枪/connector id
- 状态：Available / Preparing / Charging / Faulted 等
- 实时功率或电压电流
- 电量
- SOC 是否上报
- 故障码

如果只有 MeterValues 没有实时功率，需要确认采样 measurand：

```text
Power.Active.Import
Energy.Active.Import.Register
Voltage
Current.Import
SoC
```

## 5. 控制命令确认

先问厂家是否开放远程控制：

- RemoteStartTransaction
- RemoteStopTransaction
- ChangeConfiguration
- SetChargingProfile
- ClearChargingProfile
- Reset

限功率通常涉及 `SetChargingProfile`，不同桩支持情况差异很大。必须确认：

- 是否支持
- 单位 A/kW
- 作用范围：整桩 / connector
- 是否立即生效
- 是否有应答和失败原因

## 6. 最小通过标准

- 桩能连接到 Central System
- 能收到 BootNotification 和 Heartbeat
- 能收到 connector 状态
- 能收到电量或功率相关 MeterValues
- 是否支持远程控制已经确认
