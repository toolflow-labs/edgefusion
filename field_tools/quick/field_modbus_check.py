#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 Modbus 快速检查工具。

定位：quick 主入口，只做现场第一轮需要的事：
1. 按 field_points.yaml 读取 2-5 个关键遥测字段；
2. 对一个控制点做 dry-run 或确认写入；
3. 输出 JSON 报告。

复杂排查请使用 ../advanced/ 下的 doctor/read_table/safe_write。
"""

import argparse
import json
import struct
from datetime import datetime


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def load_points(path):
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("缺少依赖：请先安装 pyyaml，例如 pip install pyyaml==6.0.1") from exc
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def parse_number(value):
    text = str(value).strip()
    if text.lower().startswith(("0x", "-0x")):
        return int(text, 16)
    if any(ch in text for ch in ".eE"):
        number = float(text)
        return int(number) if number.is_integer() else number
    return int(text)


def signed(value, bits):
    sign_bit = 1 << (bits - 1)
    mask = 1 << bits
    return value - mask if value & sign_bit else value


def register_count(data_type):
    return 2 if str(data_type).lower() in {"u32", "i32", "f32", "float32"} else 1


def words_to_bytes(registers, word_order="big", byte_order="big"):
    words = list(registers)
    if word_order == "little":
        words = list(reversed(words))
    payload = bytearray()
    for word in words:
        payload.extend(int(word & 0xFFFF).to_bytes(2, byteorder=byte_order, signed=False))
    return bytes(payload)


def decode_registers(registers, data_type, word_order="big", byte_order="big"):
    kind = str(data_type).lower()
    if kind == "u16":
        return int(registers[0])
    if kind == "i16":
        return signed(int(registers[0]), 16)
    payload = words_to_bytes(registers[:2], word_order=word_order, byte_order=byte_order)
    unsigned = int.from_bytes(payload, byteorder="big", signed=False)
    if kind == "u32":
        return unsigned
    if kind == "i32":
        return signed(unsigned, 32)
    if kind in {"f32", "float32"}:
        return struct.unpack(">f", payload)[0]
    raise ValueError(f"不支持的 type: {data_type}")


def encode_words(value, data_type, scale=1.0, word_order="big", byte_order="big"):
    kind = str(data_type).lower()
    raw_number = float(value) / float(scale or 1)
    if kind in {"u16", "i16"}:
        raw = int(round(raw_number))
        if kind == "i16" and raw < 0:
            raw += 0x10000
        return [raw & 0xFFFF]
    if kind in {"u32", "i32"}:
        raw = int(round(raw_number))
        if kind == "i32" and raw < 0:
            raw += 0x100000000
        payload = int(raw & 0xFFFFFFFF).to_bytes(4, byteorder="big", signed=False)
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


def apply_scale(value, point):
    if not isinstance(value, (int, float)):
        return value
    scale = float(point.get("scale", 1) or 1)
    offset = float(point.get("offset", 0) or 0)
    result = value * scale + offset
    return int(result) if isinstance(result, float) and result.is_integer() else result


def apply_enum(value, point):
    enum = point.get("enum")
    if not isinstance(enum, dict):
        return value
    return enum.get(value, enum.get(str(value), value))


def make_client(args):
    try:
        from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    except ImportError as exc:
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


def read_point(client, unit_id, point):
    area = str(point.get("area", "holding")).lower()
    addr = int(parse_number(point["addr"]))
    data_type = str(point.get("type", "u16")).lower()
    try:
        if area in {"holding", "input"}:
            count = int(point.get("count", register_count(data_type)))
            if area == "holding":
                response = client.read_holding_registers(addr, count, slave=unit_id)
            else:
                response = client.read_input_registers(addr, count, slave=unit_id)
            if response.isError():
                return {"success": False, "name": point.get("name"), "detail": str(response)}
            raw = list(response.registers)
            decoded = decode_registers(
                raw,
                data_type,
                word_order=str(point.get("word_order", "big")).lower(),
                byte_order=str(point.get("byte_order", "big")).lower(),
            )
            value = apply_enum(apply_scale(decoded, point), point)
            return {"success": True, "name": point.get("name"), "addr": addr, "raw": raw, "value": value, "unit": point.get("unit", "")}
        if area in {"coil", "discrete"}:
            if area == "coil":
                response = client.read_coils(addr, 1, slave=unit_id)
            else:
                response = client.read_discrete_inputs(addr, 1, slave=unit_id)
            if response.isError():
                return {"success": False, "name": point.get("name"), "detail": str(response)}
            value = apply_enum(bool(response.bits[0]), point)
            return {"success": True, "name": point.get("name"), "addr": addr, "raw": bool(response.bits[0]), "value": value, "unit": point.get("unit", "")}
        return {"success": False, "name": point.get("name"), "detail": f"未知 area: {area}"}
    except Exception as exc:
        return {"success": False, "name": point.get("name"), "detail": str(exc)}


def write_point(client, unit_id, point, value, confirm):
    addr = int(parse_number(point["addr"]))
    words = encode_words(
        value,
        point.get("type", "u16"),
        scale=point.get("scale", 1),
        word_order=str(point.get("word_order", "big")).lower(),
        byte_order=str(point.get("byte_order", "big")).lower(),
    )
    report = {"name": point.get("name"), "addr": addr, "value": value, "words": words, "confirmed": bool(confirm), "success": True}
    if not confirm:
        report["dry_run"] = True
        report["note"] = "未加 --confirm-write，未真正写入设备"
        return report
    try:
        if len(words) == 1:
            response = client.write_register(addr, words[0], slave=unit_id)
        else:
            response = client.write_registers(addr, words, slave=unit_id)
        report["dry_run"] = False
        report["success"] = not response.isError()
        report["response"] = str(response)
        return report
    except Exception as exc:
        report["success"] = False
        report["detail"] = str(exc)
        return report


def build_parser():
    parser = argparse.ArgumentParser(description="现场 Modbus 快速读写检查。")
    subparsers = parser.add_subparsers(dest="transport", required=True)
    tcp = subparsers.add_parser("tcp")
    tcp.add_argument("--host", required=True)
    tcp.add_argument("--port", type=int, default=502)
    rtu = subparsers.add_parser("rtu")
    rtu.add_argument("--serial-port", required=True)
    rtu.add_argument("--baudrate", type=int, default=9600)
    rtu.add_argument("--bytesize", type=int, default=8)
    rtu.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"])
    rtu.add_argument("--stopbits", type=int, default=1)
    for subparser in (tcp, rtu):
        subparser.add_argument("--unit-id", type=int, required=True)
        subparser.add_argument("--points", default="field_points.yaml")
        subparser.add_argument("--timeout", type=float, default=3.0)
        subparser.add_argument("--read", action="store_true")
        subparser.add_argument("--write", help="控制写入，格式 name=value，例如 power_limit=3000")
        subparser.add_argument("--confirm-write", action="store_true")
        subparser.add_argument("--json-report")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.read and not args.write:
        parser.error("--read 或 --write 至少提供一个")
        return 2
    try:
        points = load_points(args.points)
        client = make_client(args)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not client.connect():
        print("连接失败：请检查 IP/端口、串口、波特率、485 A/B 或 unit id。")
        return 2
    report = {"tool": "field_modbus_check.py", "timestamp": now_iso(), "transport": args.transport, "unit_id": args.unit_id, "reads": [], "write": None, "success": False}
    try:
        if args.read:
            for point in points.get("telemetry", []):
                report["reads"].append(read_point(client, args.unit_id, point))
        if args.write:
            if "=" not in args.write:
                parser.error("--write 格式应为 name=value")
                return 2
            name, value = args.write.split("=", 1)
            control = next((item for item in points.get("controls", []) if item.get("name") == name), None)
            if not control:
                print(f"未在 controls 中找到控制点：{name}")
                return 2
            report["write"] = write_point(client, args.unit_id, control, parse_number(value), args.confirm_write)
    finally:
        client.close()
    read_ok = all(item.get("success") for item in report["reads"]) if report["reads"] else True
    write_ok = report["write"] is None or report["write"].get("success")
    report["success"] = read_ok and write_ok
    print("Modbus 快速检查结果")
    for item in report["reads"]:
        print(f"  READ  {item.get('name')}: success={item.get('success')} value={item.get('value')} raw={item.get('raw')}")
    if report["write"]:
        item = report["write"]
        print(f"  WRITE {item.get('name')}: dry_run={item.get('dry_run', False)} success={item.get('success')} words={item.get('words')}")
    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"已保存 JSON 报告：{args.json_report}")
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
