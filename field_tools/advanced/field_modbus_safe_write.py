#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 Modbus 安全写入工具。

默认只做 dry-run，不会真正写设备。必须显式加 --confirm-write 才会写。

示例：
  python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000
  python field_modbus_safe_write.py tcp --host 192.168.1.10 --unit-id 1 --addr 42001 --type u16 --value 3000 --confirm-write
  python field_modbus_safe_write.py rtu --serial-port COM3 --baudrate 9600 --unit-id 1 --addr 42001 --type u16 --value 3000 --confirm-write

只依赖 pymodbus，不依赖 EdgeFusion 项目代码。现场可以直接复制本文件使用。
"""

import argparse
import json
import struct


def parse_number(value):
    text = str(value).strip()
    if text.lower().startswith(("0x", "-0x")):
        return int(text, 16)
    if any(ch in text for ch in ".eE"):
        number = float(text)
        if number.is_integer():
            return int(number)
        return number
    return int(text)


def parse_write_values(text):
    # 多寄存器写入时，--values 传的是“原始寄存器值”，不会再做 scale/type 编码。
    # 适合厂家文档给出完整命令报文的情况，例如 1,0x02,3000,0。
    return [int(parse_number(part)) for part in str(text).split(",") if part.strip()]


def encode_single_value(value, data_type, scale=1.0):
    # 单寄存器写入会先反算倍率：现场输入业务值，实际写入 raw = value / scale。
    # i16 负数按补码写入。
    raw_value = int(round(float(value) / float(scale or 1)))
    kind = str(data_type).lower()
    if kind == "i16" and raw_value < 0:
        raw_value += 0x10000
    return raw_value & 0xFFFF


def encode_words(value, data_type, scale=1.0, word_order="big", byte_order="big"):
    # --value 走这里：把一个业务值编码成 1 个或 2 个寄存器。
    # 如果厂家要求固定多寄存器命令，建议直接用 --values 传原始 words，更直观。
    kind = str(data_type).lower()
    if kind in {"u16", "i16"}:
        return [encode_single_value(value, kind, scale=scale)]

    raw_number = float(value) / float(scale or 1)
    if kind in {"u32", "i32"}:
        raw_int = int(round(raw_number))
        if kind == "i32" and raw_int < 0:
            raw_int += 0x100000000
        payload = int(raw_int & 0xFFFFFFFF).to_bytes(4, byteorder="big", signed=False)
    elif kind in {"f32", "float32"}:
        payload = struct.pack(">f", float(raw_number))
    else:
        raise ValueError(f"不支持的 type: {data_type}")

    words = [
        int.from_bytes(payload[0:2], byteorder=byte_order, signed=False),
        int.from_bytes(payload[2:4], byteorder=byte_order, signed=False),
    ]
    if word_order == "little":
        words = list(reversed(words))
    return words


def make_client(args):
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


def read_holding(client, addr, count, unit_id):
    # 写前/写后读回只读 holding register。
    # 如果设备控制区不可读，这里可能返回 None，不代表写入一定失败。
    try:
        response = client.read_holding_registers(addr, count, slave=unit_id)
        if response.isError():
            return None
        return list(response.registers)
    except Exception:
        return None


def build_parser():
    parser = argparse.ArgumentParser(description="现场 Modbus 安全写入。默认 dry-run，不真正写。")
    subparsers = parser.add_subparsers(dest="transport", required=True)

    tcp = subparsers.add_parser("tcp", help="写 Modbus TCP")
    tcp.add_argument("--host", required=True)
    tcp.add_argument("--port", type=int, default=502)

    rtu = subparsers.add_parser("rtu", help="写 Modbus RTU")
    rtu.add_argument("--serial-port", required=True)
    rtu.add_argument("--baudrate", type=int, default=9600)
    rtu.add_argument("--bytesize", type=int, default=8)
    rtu.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"])
    rtu.add_argument("--stopbits", type=int, default=1)

    for subparser in (tcp, rtu):
        subparser.add_argument("--unit-id", type=int, required=True)
        subparser.add_argument("--addr", type=int, required=True, help="写入 holding register 地址")
        subparser.add_argument("--type", default="u16", help="u16/i16/u32/i32/f32，默认 u16")
        subparser.add_argument("--scale", type=float, default=1.0)
        subparser.add_argument("--word-order", default="big", choices=["big", "little"])
        subparser.add_argument("--byte-order", default="big", choices=["big", "little"])
        subparser.add_argument("--value", help="单值写入，例如 3000 或 0x10")
        subparser.add_argument("--values", help="多寄存器原始值，逗号分隔，例如 1,0x02,3000,0")
        subparser.add_argument("--confirm-write", action="store_true", help="确认真正写入设备")
        subparser.add_argument("--timeout", type=float, default=3.0)
        subparser.add_argument("--json-report", help="把结果保存成 JSON 文件")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # 为了避免现场误操作，必须明确是写单个业务值，还是写一组原始寄存器。
    if not args.value and not args.values:
        parser.error("--value 或 --values 必须提供一个")
        return 2
    if args.value and args.values:
        parser.error("--value 和 --values 只能提供一个")
        return 2

    try:
        words = (
            parse_write_values(args.values)
            if args.values
            else encode_words(
                parse_number(args.value),
                args.type,
                scale=args.scale,
                word_order=args.word_order,
                byte_order=args.byte_order,
            )
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    try:
        client = make_client(args)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not client.connect():
        print("连接失败：请先用 field_modbus_doctor.py 排查链路。")
        return 2

    report = {
        "transport": args.transport,
        "unit_id": args.unit_id,
        "addr": args.addr,
        "type": args.type,
        "words": words,
        "confirmed": bool(args.confirm_write),
        "before": None,
        "after": None,
        "success": False,
    }

    try:
        # 先读一次，方便判断写入前设备控制区状态；读不到也继续允许写。
        report["before"] = read_holding(client, args.addr, len(words), args.unit_id)

        if not args.confirm_write:
            # 默认 dry-run：现场先看将要写入的 raw words，确认后再加 --confirm-write。
            print("DRY-RUN：没有写入设备。确认无误后加 --confirm-write 才会真正写。")
            print(f"计划写入：unit={args.unit_id}, addr={args.addr}, words={words}")
            report["success"] = True
            return_code = 0
        else:
            # 真正写入只在 --confirm-write 下执行。
            # 1 个 word 用 function 06，多 word 用 function 16。
            if len(words) == 1:
                response = client.write_register(args.addr, words[0], slave=args.unit_id)
            else:
                response = client.write_registers(args.addr, words, slave=args.unit_id)
            report["success"] = not response.isError()
            report["write_response"] = str(response)
            report["after"] = read_holding(client, args.addr, len(words), args.unit_id)
            return_code = 0 if report["success"] else 2
    finally:
        client.close()

    print("写入结果")
    print(f"  success : {report['success']}")
    print(f"  unit    : {args.unit_id}")
    print(f"  addr    : {args.addr}")
    print(f"  words   : {words}")
    print(f"  before  : {report['before']}")
    print(f"  after   : {report['after']}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"\n已保存 JSON 报告：{args.json_report}")

    return return_code


if __name__ == "__main__":
    exit(main())
