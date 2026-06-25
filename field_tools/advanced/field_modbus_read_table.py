#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 Modbus 点表批量读取工具。

使用方式：
1. 打开本文件，修改最上面的 FIELDS。
2. 运行 TCP 或 RTU 命令。
3. 看表格里的 raw/value/unit/result。

示例：
  python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1
  python field_modbus_read_table.py rtu --serial-port COM3 --baudrate 9600 --unit-id 1
  python field_modbus_read_table.py tcp --host 192.168.1.10 --unit-id 1 --probe-offsets

只依赖 pymodbus，不依赖 EdgeFusion 项目代码。现场可以直接复制本文件使用。
"""

import argparse
import json
import struct


# 现场最常改这里。先填 2-5 个关键字段，不要一上来抄完整点表。
#
# 字段说明：
# - name: 字段名，随便起，但建议用 power/soc/status/mode 这类业务语义
# - area: holding/input/coil/discrete。普通寄存器多为 holding 或 input
# - addr: 文档里的寄存器地址。若怀疑 30001/40001 基址问题，运行时加 --probe-offsets
# - type: u16/i16/u32/i32/f32。32 位字段会读两个连续寄存器
# - scale: 倍率。最终显示值 = 原始值 * scale + offset
# - unit: 只用于显示，不参与计算
# - word_order: 32 位字段的寄存器顺序，big 表示高字在前，little 表示低字在前
# - byte_order: 单个 16 位字内部的字节顺序，绝大多数设备用 big
# - enum: 状态码映射，例如 {0: "offline", 1: "online"}
FIELDS = [
    # {"name": "soc", "area": "holding", "addr": 32001, "type": "u16", "scale": 1, "unit": "%"},
    # {"name": "power", "area": "holding", "addr": 32002, "type": "i32", "scale": 0.1, "unit": "kW"},
    # {"name": "status", "area": "input", "addr": 30001, "type": "u16", "enum": {0: "offline", 1: "online"}},
]


# 寄存器区：返回 registers，需要按 type/scale/word_order 解码。
REGISTER_AREAS = {
    "holding": "read_holding_registers",
    "input": "read_input_registers",
}

# 位区：返回 bits，只读取 bool 值。
BIT_AREAS = {
    "coil": "read_coils",
    "discrete": "read_discrete_inputs",
}


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


def register_count(data_type):
    # u32/i32/f32 占两个 16 位寄存器，其余默认占一个。
    kind = str(data_type).lower()
    if kind in {"u32", "i32", "f32", "float32"}:
        return 2
    return 1


def signed(value, bits):
    sign_bit = 1 << (bits - 1)
    mask = 1 << bits
    return value - mask if value & sign_bit else value


def words_to_bytes(registers, word_order="big", byte_order="big"):
    # word_order 处理两个 16 位寄存器的前后顺序。
    # byte_order 处理每个 16 位寄存器内部两个字节的顺序。
    # 大多数 Modbus 设备是 word_order=big, byte_order=big；
    # 如果 32 位功率/SOC 明显不对，现场优先尝试 word_order=little。
    words = list(registers)
    if word_order == "little":
        words = list(reversed(words))
    output = bytearray()
    for word in words:
        output.extend(int(word & 0xFFFF).to_bytes(2, byteorder=byte_order, signed=False))
    return bytes(output)


def decode_registers(registers, data_type, word_order="big", byte_order="big"):
    # 本工具只实现现场最常见的基础类型。
    # 遇到 BCD、bit field、厂家私有格式时，先用 raw 值记录下来，回来再沉淀正式 profile。
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


def build_address_candidates(addr, probe_offsets=False):
    # 厂家文档常写 40001/30001，但 pymodbus 通常要传 0 基地址。
    # --probe-offsets 会把 40001 试成 0/1，也会试 addr-1/addr/addr+1。
    if not probe_offsets:
        return [addr]

    candidates = []
    if 40001 <= addr <= 49999:
        base = addr - 40001
        candidates.extend([base, base + 1])
    elif 30001 <= addr <= 39999:
        base = addr - 30001
        candidates.extend([base, base + 1])
    elif 10001 <= addr <= 19999:
        base = addr - 10001
        candidates.extend([base, base + 1])

    candidates.extend([addr - 1, addr, addr + 1])
    return [item for item in dict.fromkeys(candidates) if item >= 0]


def apply_scale(value, field):
    # 只对数字做倍率和偏移；状态字符串、bool 等保持原样。
    if not isinstance(value, (int, float)):
        return value
    scale = float(field.get("scale", 1) or 1)
    offset = float(field.get("offset", 0) or 0)
    result = value * scale + offset
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


def apply_enum(value, field):
    # enum 允许 key 写数字或字符串，便于现场快速修改。
    enum = field.get("enum")
    if not isinstance(enum, dict):
        return value
    for candidate in (value, str(value)):
        if candidate in enum:
            return enum[candidate]
    return value


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


def read_one(client, unit_id, field, addr):
    area = str(field.get("area", "holding")).lower()
    data_type = str(field.get("type", "u16")).lower()

    try:
        if area in REGISTER_AREAS:
            # holding/input register：先读原始 registers，再按 type 解码。
            count = int(field.get("count", register_count(data_type)))
            if area == "holding":
                response = client.read_holding_registers(addr, count, slave=unit_id)
            else:
                response = client.read_input_registers(addr, count, slave=unit_id)
            if response.isError():
                return {"success": False, "raw": None, "value": None, "detail": str(response)}
            raw = list(response.registers)
            decoded = decode_registers(
                raw,
                data_type,
                word_order=str(field.get("word_order", "big")).lower(),
                byte_order=str(field.get("byte_order", "big")).lower(),
            )
            value = apply_enum(apply_scale(decoded, field), field)
            return {"success": True, "raw": raw, "value": value, "detail": "ok"}

        if area in BIT_AREAS:
            # coil/discrete input：只读一个 bit，适合运行/故障开关量。
            if area == "coil":
                response = client.read_coils(addr, 1, slave=unit_id)
            else:
                response = client.read_discrete_inputs(addr, 1, slave=unit_id)
            if response.isError():
                return {"success": False, "raw": None, "value": None, "detail": str(response)}
            raw_value = bool(response.bits[0])
            value = apply_enum(raw_value, field)
            return {"success": True, "raw": raw_value, "value": value, "detail": "ok"}

        return {"success": False, "raw": None, "value": None, "detail": f"未知 area: {area}"}
    except Exception as exc:
        return {"success": False, "raw": None, "value": None, "detail": f"exception: {exc}"}


def read_field(client, unit_id, field, probe_offsets=False):
    addr = int(parse_number(field["addr"]))
    attempts = []
    # 默认只读给定地址；加 --probe-offsets 后会尝试多个候选地址，首个成功即返回。
    for candidate in build_address_candidates(addr, probe_offsets=probe_offsets):
        result = read_one(client, unit_id, field, candidate)
        attempts.append({"addr": candidate, **result})
        if result["success"]:
            return {"field": field, "addr": candidate, "attempts": attempts, **result}
    return {"field": field, "addr": addr, "attempts": attempts, **attempts[-1]}


def print_table(rows):
    print("field                 area      addr    type   raw             value           unit   result")
    print("--------------------  --------  ------  -----  --------------  --------------  -----  ------")
    for row in rows:
        field = row["field"]
        result = "OK" if row["success"] else "FAIL"
        raw = str(row["raw"])
        value = str(row["value"])
        print(
            f"{str(field.get('name', 'unnamed')):<20}  "
            f"{str(field.get('area', 'holding')):<8}  "
            f"{row['addr']:<6}  "
            f"{str(field.get('type', 'u16')):<5}  "
            f"{raw:<14}  "
            f"{value:<14}  "
            f"{str(field.get('unit', '')):<5}  "
            f"{result} {row['detail'] if not row['success'] else ''}"
        )


def build_parser():
    parser = argparse.ArgumentParser(description="现场 Modbus 点表批量读取。")
    subparsers = parser.add_subparsers(dest="transport", required=True)

    tcp = subparsers.add_parser("tcp", help="读取 Modbus TCP")
    tcp.add_argument("--host", required=True)
    tcp.add_argument("--port", type=int, default=502)

    rtu = subparsers.add_parser("rtu", help="读取 Modbus RTU")
    rtu.add_argument("--serial-port", required=True)
    rtu.add_argument("--baudrate", type=int, default=9600)
    rtu.add_argument("--bytesize", type=int, default=8)
    rtu.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"])
    rtu.add_argument("--stopbits", type=int, default=1)

    for subparser in (tcp, rtu):
        subparser.add_argument("--unit-id", type=int, required=True)
        subparser.add_argument("--timeout", type=float, default=3.0)
        subparser.add_argument("--only", help="只读取一个字段名")
        subparser.add_argument("--probe-offsets", action="store_true", help="尝试 addr-1/addr/addr+1 和 30001/40001 基址换算")
        subparser.add_argument("--json-report", help="把结果保存成 JSON 文件")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    fields = [field for field in FIELDS if not args.only or field.get("name") == args.only]
    if not fields:
        print("没有可读取字段：请先编辑本文件顶部的 FIELDS，或检查 --only 字段名。")
        return 2

    try:
        client = make_client(args)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not client.connect():
        print("连接失败：请先用 field_modbus_doctor.py 排查链路。")
        return 2

    try:
        # 每个字段独立读取；某个字段失败不会影响其他字段继续读。
        rows = [read_field(client, args.unit_id, field, probe_offsets=args.probe_offsets) for field in fields]
    finally:
        client.close()

    print_table(rows)
    if args.json_report:
        serializable = []
        for row in rows:
            item = {key: value for key, value in row.items() if key != "field"}
            item["field"] = row["field"]
            serializable.append(item)
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(serializable, handle, ensure_ascii=False, indent=2)
        print(f"\n已保存 JSON 报告：{args.json_report}")

    return 0 if any(row["success"] for row in rows) else 2


if __name__ == "__main__":
    exit(main())
