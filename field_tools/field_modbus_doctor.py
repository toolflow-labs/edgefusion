#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 Modbus 连通性诊断工具。

用途：
1. 先确认 TCP/RTU 链路能不能连上。
2. 扫描常见 unit id。
3. 尝试 holding/input/coil/discrete 四类基本读取，判断是没响应、地址不对还是功能码不支持。

最常用：
  python field_modbus_doctor.py tcp --host 192.168.1.10 --unit-range 1-10
  python field_modbus_doctor.py rtu --serial-port COM3 --baudrate 9600 --unit-range 1-10

只依赖 pymodbus，不依赖 EdgeFusion 项目代码。现场可以直接复制本文件使用。
"""

import argparse
import json


# Modbus 常见的 4 类读取区。
# 现场第一轮排查时，不确定厂家点表到底落在哪个区，可以同时尝试 holding/input。
# coil/discrete 是位读取，部分设备不支持，失败时通常会返回 illegal function。
AREAS = {
    "holding": ("03 holding", "read_holding_registers"),
    "input": ("04 input", "read_input_registers"),
    "coil": ("01 coil", "read_coils"),
    "discrete": ("02 discrete", "read_discrete_inputs"),
}


def parse_unit_range(text):
    """Parse strings like '1-3,7' into [1, 2, 3, 7].

    现场经常不确定从站地址，所以命令行允许写：
    - 1
    - 1-10
    - 1,3,7
    - 1-10,20
    """
    units = []
    for raw_part in str(text).split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            step = 1 if end >= start else -1
            units.extend(range(start, end + step, step))
            continue
        units.append(int(part))
    return list(dict.fromkeys(units))


def parse_areas(text):
    areas = [item.strip().lower() for item in str(text).split(",") if item.strip()]
    unknown = [area for area in areas if area not in AREAS]
    if unknown:
        raise ValueError(f"未知 area: {', '.join(unknown)}")
    return areas or ["holding"]


def response_error(response):
    # pymodbus 的异常响应不是 Python exception，而是 response.isError()。
    # 这里统一转成字符串，方便现场直接看输出。
    if response is None:
        return "no response"
    is_error = getattr(response, "isError", None)
    if callable(is_error) and is_error():
        return str(response)
    return None


def summarize_response(response):
    if hasattr(response, "registers"):
        return f"registers={list(response.registers)}"
    if hasattr(response, "bits"):
        return f"bits={list(response.bits)[:8]}"
    return str(response)


def make_client(args):
    # 懒加载 pymodbus：这样现场机器没装依赖时，`--help` 仍然能正常显示。
    try:
        from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    except ImportError as exc:  # pragma: no cover - shown to field users, not unit tests
        raise RuntimeError("缺少依赖：请先安装 pymodbus，例如 pip install pymodbus==3.5.4") from exc

    if args.transport == "tcp":
        return ModbusTcpClient(args.host, port=args.port, timeout=args.timeout)
    return ModbusSerialClient(
        port=args.serial_port,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
    )


def run_read(client, area, addr, count, unit_id):
    # 只做最小读取，不做复杂解码。这里故意写得直白，现场需要改时不用追抽象。
    try:
        if area == "holding":
            response = client.read_holding_registers(addr, count, slave=unit_id)
        elif area == "input":
            response = client.read_input_registers(addr, count, slave=unit_id)
        elif area == "coil":
            response = client.read_coils(addr, count, slave=unit_id)
        elif area == "discrete":
            response = client.read_discrete_inputs(addr, count, slave=unit_id)
        else:
            return False, f"unknown area: {area}"
    except Exception as exc:
        return False, f"exception: {exc}"

    error = response_error(response)
    if error:
        return False, error
    return True, summarize_response(response)


def print_table(rows):
    print("unit  area          addr  result  detail")
    print("----  ------------  ----  ------  ------")
    for row in rows:
        result = "OK" if row["success"] else "FAIL"
        print(f"{row['unit_id']:<4}  {row['area_label']:<12}  {row['addr']:<4}  {result:<6}  {row['detail']}")


def build_parser():
    parser = argparse.ArgumentParser(description="现场 Modbus TCP/RTU 连通性诊断。")
    subparsers = parser.add_subparsers(dest="transport", required=True)

    tcp = subparsers.add_parser("tcp", help="诊断 Modbus TCP")
    tcp.add_argument("--host", required=True, help="设备 IP，例如 192.168.1.10")
    tcp.add_argument("--port", type=int, default=502)

    rtu = subparsers.add_parser("rtu", help="诊断 Modbus RTU")
    rtu.add_argument("--serial-port", required=True, help="串口，例如 COM3 或 /dev/ttyUSB0")
    rtu.add_argument("--baudrate", type=int, default=9600)
    rtu.add_argument("--bytesize", type=int, default=8)
    rtu.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"])
    rtu.add_argument("--stopbits", type=int, default=1)

    for subparser in (tcp, rtu):
        subparser.add_argument("--timeout", type=float, default=3.0, help="单次请求超时秒数")
        subparser.add_argument("--unit-range", default="1", help="unit id 范围，例如 1、1-10、1,3,7")
        subparser.add_argument("--addr", type=int, default=0, help="测试读取起始地址，默认 0")
        subparser.add_argument("--count", type=int, default=1, help="测试读取数量，默认 1")
        subparser.add_argument(
            "--areas",
            default="holding,input",
            help="逗号分隔：holding,input,coil,discrete。默认 holding,input",
        )
        subparser.add_argument("--json-report", help="把结果保存成 JSON 文件")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        units = parse_unit_range(args.unit_range)
        areas = parse_areas(args.areas)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    try:
        client = make_client(args)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not client.connect():
        print("连接失败：请检查 IP/端口、串口号、波特率、接线、485 A/B 是否接反。")
        return 2

    rows = []
    try:
        # 对每个 unit id 和 area 做一次最小读取。
        # 只要有一个 OK，就说明至少链路/从站/功能码中有一条路径是通的。
        for unit_id in units:
            for area in areas:
                success, detail = run_read(client, area, args.addr, args.count, unit_id)
                rows.append(
                    {
                        "transport": args.transport,
                        "unit_id": unit_id,
                        "area": area,
                        "area_label": AREAS[area][0],
                        "addr": args.addr,
                        "count": args.count,
                        "success": success,
                        "detail": detail,
                    }
                )
    finally:
        client.close()

    print_table(rows)
    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False, indent=2)
        print(f"\n已保存 JSON 报告：{args.json_report}")

    return 0 if any(row["success"] for row in rows) else 2


if __name__ == "__main__":
    exit(main())
