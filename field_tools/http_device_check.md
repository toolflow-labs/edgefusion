# HTTP 设备最小确认清单

HTTP 设备优先用 `curl` 或 Postman 确认，不急着写程序。目标是拿到稳定的 URL、鉴权方式和字段路径。

## 1. 先确认网络

```powershell
ping 192.168.1.20
```

如果设备禁 ping，不代表 HTTP 不通，继续测端口：

```powershell
curl -v http://192.168.1.20/
```

## 2. 确认接口入口

需要厂家明确：

- base URL
- 是否 HTTP 或 HTTPS
- 端口
- 是否需要账号密码、Token、Cookie、证书
- 是否有接口文档

记录：

```text
base_url =
auth =
doc =
```

## 3. 读取状态接口

无鉴权示例：

```powershell
curl -v http://192.168.1.20/api/status
```

Bearer Token 示例：

```powershell
curl -v -H "Authorization: Bearer TOKEN" http://192.168.1.20/api/status
```

Basic 认证示例：

```powershell
curl -v -u user:password http://192.168.1.20/api/status
```

把响应保存下来：

```powershell
curl http://192.168.1.20/api/status -o http_status_sample.json
```

## 4. 判断响应格式

优先确认是不是 JSON：

```json
{
  "power": 12345,
  "status": "normal",
  "soc": 78
}
```

如果不是 JSON，记录真实格式：

- JSON
- XML
- HTML 页面
- 纯文本
- 二进制
- 厂家私有

非 JSON 不建议第一次就做通用运行时，先保存样例回开发环境分析。

## 5. 标出字段路径

按统一语义标注：

```text
power        -> $.power
status       -> $.status
soc          -> $.battery.soc
mode         -> $.mode
power_limit  -> $.control.powerLimit
```

同时记录：

- 单位
- 倍率
- 正负号方向
- 状态码含义
- 数据更新时间字段

## 6. 控制接口

先问厂家是否允许控制。不要直接对生产设备试高风险控制。

POST JSON 示例：

```powershell
curl -v -X POST http://192.168.1.20/api/control `
  -H "Content-Type: application/json" `
  -d "{\"cmd\":\"set_power_limit\",\"value\":3000}"
```

记录：

- URL
- method
- headers
- body 示例
- 成功响应
- 失败响应
- 是否有 ack
- 是否能读回控制结果

## 7. 最小通过标准

- 能访问设备 HTTP 服务
- 能拿到至少一个状态接口响应
- 能标出核心字段路径
- 能确认鉴权方式
- 如需控制，厂家明确允许且有安全测试值
