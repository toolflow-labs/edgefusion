# Docs Guide

如果你现在只想知道“该看哪个文档”，先看这里。

## 现在优先看

### 1. Linux 工控机部署、更新与维护

看 [linux-ipc-deployment-guide.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/linux-ipc-deployment-guide.md)

适合场景：

- 第一次把 EdgeFusion 部署到 Linux 工控机
- 想弄清楚命令到底在哪台机器上执行
- 想补齐网络配置、升级、回滚、备份、恢复的完整流程
- 手头没有设备，想先用 VirtualBox 把部署链路跑通

### 2. 设备模型与正式字段

看 [device-models-and-adaptation.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/device-models-and-adaptation.md)

适合场景：

- 想确认系统当前支持哪些设备模型
- 想确认 `telemetry_map / control_map` 的正式口径
- 想知道储能、充电桩、光伏、总表各自的核心字段

这是当前最重要的主文档。

### 3. 真机 Modbus 快速接入

看 [modbus-device-onboarding-fast-path.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/modbus-device-onboarding-fast-path.md)

适合场景：

- 厂家刚给了 Modbus Excel / PDF
- 想先把一台真实设备最快接通
- 想知道先摘哪些字段、先读哪些点、什么时候再补控制

如果你只想看最短 checklist 和最小字段表，直接看 [device-onboarding-cheatsheet.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/device-onboarding-cheatsheet.md)

### 4. 可复制模板

看 [modbus-explicit-mapping-templates.yaml](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/examples/modbus-explicit-mapping-templates.yaml)

适合场景：

- 需要直接开始填储能或充电桩映射
- 想先走显式映射联调

## 需要深入架构时再看

看 [architecture-layering-and-device-adaptation.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/architecture-layering-and-device-adaptation.md)

适合场景：

- 要讨论 Modbus / MQTT / HTTP / CAN 的分层边界
- 要讨论 profile、protocol、transport 应该落在哪一层
- 要做中长期架构演进

这份文档不是你接第一台真机时的首选入口。

## 现在可以忽略

`docs/superpowers/`

这部分主要是开发过程中的计划文档，不是项目使用文档，也不是现场接入手册。

## 推荐阅读顺序

1. [linux-ipc-deployment-guide.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/linux-ipc-deployment-guide.md)
2. [device-models-and-adaptation.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/device-models-and-adaptation.md)
3. [device-onboarding-cheatsheet.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/device-onboarding-cheatsheet.md)
4. [modbus-device-onboarding-fast-path.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/modbus-device-onboarding-fast-path.md)
5. [modbus-explicit-mapping-templates.yaml](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/examples/modbus-explicit-mapping-templates.yaml)
6. [architecture-layering-and-device-adaptation.md](/C:/Users/Lenovo/Desktop/桌面工作空间/终端台区智能化项目/后台项目/edgefusion/docs/architecture-layering-and-device-adaptation.md)
