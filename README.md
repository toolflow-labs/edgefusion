# EdgeFusion - 台区智能融合终端后台系统

基于 Python 的台区智能融合终端后台程序，用于对台区内的光伏、储能、充电桩等设备进行协同控制和监控。

项目定位如下：

- Linux 是正式部署环境，推荐通过 `deploy.sh` 完成首次部署
- Windows 的 `start.bat` 仅用于开发和联调阶段的一键启动

## 功能特性

- **设备管理**：支持光伏、储能、充电桩等设备接入（Modbus TCP/RTU、MQTT、OCPP）
- **型号配置**：支持不同型号充电桩的点表配置（120kW/240kW直流桩、通用桩）
- **设备模拟器**：内置 Modbus 充电桩模拟器，支持双枪充电、功率限制等高级功能
- **Web监控面板**：实时监测设备状态和充电枪数据，提供可视化界面
- **设备控制**：支持启动/停止充电、功率限制调节、急停等远程控制
- **控制策略**：支持削峰填谷、需求响应、自发自用等策略
- **数据采集**：定期采集设备数据并存储到 SQLite 数据库

## 快速开始

### Linux 正式部署

```bash
chmod +x deploy.sh run_local.sh backup.sh restore.sh uninstall.sh
sudo ./deploy.sh
```

`deploy.sh` 会自动完成以下动作：

- 在未预设 `EDGEFUSION_*` 时交互式提示服务名、用户和目录，回车直接使用默认值
- 将当前源码目录同步到标准 Linux 目录
- 创建/复用 `.venv`
- 安装生产依赖 `requirements-prod.txt`
- 生成并安装 `systemd` 服务
- `daemon-reload`
- 启动或重启服务

默认部署目录遵循 Linux 常见约定：

- 程序目录：`/opt/edgefusion`
- 配置目录：`/etc/edgefusion`
- 数据目录：`/var/lib/edgefusion`
- 日志目录：`/var/log/edgefusion`

如需自定义用户、服务名或目录，可使用环境变量：

```bash
sudo \
  EDGEFUSION_USER=edgefusion \
  EDGEFUSION_SERVICE_NAME=edgefusion \
  EDGEFUSION_APP_DIR=/opt/edgefusion \
  EDGEFUSION_CONFIG_DIR=/etc/edgefusion \
  EDGEFUSION_DATA_DIR=/var/lib/edgefusion \
  EDGEFUSION_LOG_DIR=/var/log/edgefusion \
  ./deploy.sh
```

后续升级时，在新的源码目录执行同一条 `sudo ./deploy.sh` 即可，已有配置、数据库和日志会保留。

如需完全跳过交互，可同时传入 `EDGEFUSION_*` 和 `EDGEFUSION_NONINTERACTIVE=1`。本地联调请使用 `run_local.sh` 或 Windows 下的 `start.bat`。详见 [DEPLOYMENT.md](DEPLOYMENT.md)。

如果需要卸载 Linux 生产部署：

```bash
sudo ./uninstall.sh
```

默认只卸载服务和程序目录，保留配置、数据库和日志。若要连生产状态一起清理：

```bash
sudo ./uninstall.sh --purge
```

### Windows 开发联调

首次运行直接执行：

```bat
start.bat
```

`start.bat` 会自动执行以下动作：

- 检测并创建 `.venv`
- 安装 `requirements.txt`
- 启动 `python -m edgefusion.main`

如需强制重装依赖，可执行：

```bat
start.bat --reinstall
```

### 手动启动主程序

Linux 本地联调推荐直接执行：

```bash
./run_local.sh
```

`run_local.sh` 会自动检测 Python 3.10/3.11/3.12、创建 `.venv`、安装 `requirements.txt`，然后以项目目录下的本地路径语义启动程序。  
如需强制重装依赖，可执行：

```bash
./run_local.sh --reinstall
```

如果你希望手动使用虚拟环境，建议使用 Python 3.10、3.11 或 3.12：

```bash
python3.10 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m edgefusion.main
```

```powershell
# Windows PowerShell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m edgefusion.main
```

### 访问 Web 界面

启动成功后，打开浏览器访问：**http://localhost:5000**

## 联调说明

联调时可先启动 Modbus 模拟器：

```bash
# 启动 120kW 双枪直流桩模拟器
python modbus_charger_simulator.py --model xj_dc_120kw

# 或启动 240kW 型号
python modbus_charger_simulator.py --model xj_dc_240kw

# 或启动通用充电桩
python modbus_charger_simulator.py --model generic
```

也可以运行：

```bash
python quick_test.py
```

该脚本用于联调辅助和依赖检查，不是正式部署入口。

## 文档

- [docs/linux-ipc-deployment-guide.md](docs/linux-ipc-deployment-guide.md) - 面向新手的 Linux 工控机部署、更新、维护与 VirtualBox 验证手册
- [DEPLOYMENT.md](DEPLOYMENT.md) - Linux 部署与 `systemd` 运维说明
- [USAGE.md](USAGE.md) - 联调、模拟器、Web 界面和 API 使用说明
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构和技术选型说明
- [docs/device-models-and-adaptation.md](docs/device-models-and-adaptation.md) - 光、储、充、总表当前统一模型与现场接入适配说明
- [docs/architecture-layering-and-device-adaptation.md](docs/architecture-layering-and-device-adaptation.md) - 设备模型、协议适配、传输和物理连接的目标分层说明

## 项目结构

```text
edgefusion/
├── edgefusion/
│   ├── main.py
│   ├── config.py
│   ├── device_manager.py
│   ├── adapters/
│   ├── point_tables.py
│   ├── protocol/
│   ├── strategy/
│   ├── monitor/
│   └── simulator/
├── config.yaml
├── requirements.txt
├── start.bat
├── deploy.sh
├── runtime-env.sh
├── run_local.sh
├── backup.sh
├── restore.sh
├── uninstall.sh
├── edgefusion.service.template
└── DEPLOYMENT.md
```

## 支持的设备型号

| 型号 | 协议 | 最大功率 | 枪数 | 特点 |
|------|------|----------|------|------|
| 120kW 直流桩 | Modbus TCP | 120kW | 2 | 支持功率限制、SOC 监控 |
| 240kW 直流桩 | Modbus TCP | 240kW | 2 | 支持功率限制、SOC 监控 |
| 通用充电桩 | Modbus TCP/RTU | - | 1 | 简单寄存器映射 |

## 版本信息

- **版本**：0.3.0
- **更新日期**：2026-02-26

## 许可证

本项目仅供学习和研究使用。
