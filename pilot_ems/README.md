# Pilot EMS

Pilot EMS 是第一次试点用的极简运行时。它不复用 EdgeFusion 的型号目录、profile registry、自动发现和候选设备流程。

## 目标

- 显式配置现场设备和字段
- 周期采集总表、光伏、储能、充电桩
- 展示最新值和错误
- 提供白名单控制接口
- 显示简单模式判断和反送保护动作计划

## 启动

复制配置：

```powershell
Copy-Item pilot_ems\config.example.yaml pilot_ems\config.local.yaml
```

按 `field_tools` 测出来的地址、倍率、unit id 修改配置，然后启动：

```powershell
.\.venv\Scripts\python.exe -m pilot_ems.app --config pilot_ems\config.local.yaml --port 5050
```

打开：

```text
http://localhost:5050
```

## 控制接口

控制字段必须先写在配置的 `controls` 里，并带 `min/max`。

```powershell
Invoke-RestMethod -Method Post http://localhost:5050/api/control `
  -ContentType "application/json" `
  -Body '{"device_id":"pv_1","field":"power_limit","value":3000}'
```

充电枪控制用内部业务对象 id：

```powershell
Invoke-RestMethod -Method Post http://localhost:5050/api/control `
  -ContentType "application/json" `
  -Body '{"device_id":"charger_1.gun1","field":"power_limit","value":60}'
```

## 现场顺序

```text
field_tools 确认接入方式和字段
  -> 填 pilot_ems/config.local.yaml
  -> 启动 Pilot EMS 看 dashboard
  -> 人工触发安全控制
  -> 根据 latest snapshot 看模式判断
```
