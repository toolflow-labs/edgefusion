# CAN 设备最小确认清单

CAN 不是完整业务协议。现场不能只记录“支持 CAN”，必须确认应用层到底是什么。

## 1. 先确认 CAN 类型

记录：

```text
CAN / CAN FD =
波特率 =
通道 =
接口设备 = USB-CAN / PCIe CAN / 网关 / 其他
应用层 = CANopen / J1939 / 厂家私有 / 未知
```

如果应用层未知，第一次试点不建议直接承诺接入。

## 2. 厂家必须提供的信息

至少需要：

- 帧 ID 或对象字典
- 周期帧还是请求响应
- 字节序
- 字段 offset
- 数据类型
- 倍率
- 状态码
- 控制帧格式
- 是否需要心跳或节点管理

CANopen 需要：

- Node ID
- Object Dictionary
- PDO/SDO 映射
- NMT 状态要求

J1939 需要：

- PGN
- SPN
- 源地址
- 请求方式

厂家私有协议需要完整帧定义。

## 3. 现场抓包

Linux 常见工具：

```bash
ip link
ip link set can0 up type can bitrate 250000
candump can0
```

保存抓包：

```bash
candump -L can0 > can_capture.log
```

Windows 需要根据 USB-CAN 厂家工具导出日志。

## 4. 字段确认

对每个核心字段记录：

```text
字段 =
帧 ID / PGN / 对象索引 =
byte offset =
type =
byte order =
scale =
unit =
刷新周期 =
```

核心字段建议：

- 总表：power
- 光伏：power/status
- 储能：soc/power/mode
- 充电桩：status/power

## 5. 控制确认

不要现场盲发控制帧。必须厂家确认：

- 控制帧 ID
- payload 格式
- min/max
- 是否需要校验
- 是否需要计数器
- 是否需要应答帧
- 错误或拒绝控制的响应

## 6. 最小通过标准

- CAN 物理链路能抓到稳定帧
- 应用层协议明确
- 至少一个核心遥测字段能从帧中解释出来
- 控制帧格式有厂家确认
