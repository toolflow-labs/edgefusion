import struct


def signed(value, bits):
    sign_bit = 1 << (bits - 1)
    mask = 1 << bits
    return value - mask if value & sign_bit else value


def words_to_bytes(registers, word_order="big", byte_order="big"):
    words = list(registers)
    if word_order == "little":
        words = list(reversed(words))

    data = bytearray()
    for word in words:
        data.extend(int(word & 0xFFFF).to_bytes(2, byteorder=byte_order, signed=False))
    return bytes(data)


def _count_for(field):
    data_type = str(field.get("type", "u16")).lower()
    if data_type in ("u32", "i32", "f32", "float32"):
        return 2
    return 1


def decode_registers(registers, field):
    data_type = str(field.get("type", "u16")).lower()
    if data_type == "u16":
        value = int(registers[0])
    elif data_type == "i16":
        value = signed(int(registers[0]), 16)
    else:
        data = words_to_bytes(
            registers[:2],
            word_order=str(field.get("word_order", "big")).lower(),
            byte_order=str(field.get("byte_order", "big")).lower(),
        )
        raw = int.from_bytes(data, byteorder="big", signed=False)
        if data_type == "u32":
            value = raw
        elif data_type == "i32":
            value = signed(raw, 32)
        elif data_type in ("f32", "float32"):
            value = struct.unpack(">f", data)[0]
        else:
            raise ValueError(f"unsupported type: {field.get('type')}")

    value = value * float(field.get("scale", 1) or 1) + float(field.get("offset", 0) or 0)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def encode_words(value, field):
    data_type = str(field.get("type", "u16")).lower()
    raw_value = float(value) / float(field.get("scale", 1) or 1)

    if data_type in ("u16", "i16"):
        raw_int = int(round(raw_value))
        if data_type == "i16" and raw_int < 0:
            raw_int += 0x10000
        return [raw_int & 0xFFFF]

    if data_type in ("u32", "i32"):
        raw_int = int(round(raw_value))
        if data_type == "i32" and raw_int < 0:
            raw_int += 0x100000000
        data = int(raw_int & 0xFFFFFFFF).to_bytes(4, byteorder="big", signed=False)
    elif data_type in ("f32", "float32"):
        data = struct.pack(">f", float(raw_value))
    else:
        raise ValueError(f"unsupported type: {field.get('type')}")

    byte_order = str(field.get("byte_order", "big")).lower()
    words = [
        int.from_bytes(data[0:2], byteorder=byte_order, signed=False),
        int.from_bytes(data[2:4], byteorder=byte_order, signed=False),
    ]
    if str(field.get("word_order", "big")).lower() == "little":
        words = list(reversed(words))
    return words


def apply_enum(value, field):
    enum = field.get("enum")
    if not isinstance(enum, dict):
        return value
    for key in (value, str(value)):
        if key in enum:
            return enum[key]
    return value


def make_client(connection):
    try:
        from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    except ImportError as exc:
        raise RuntimeError("missing pymodbus; run pip install pymodbus==3.5.4") from exc

    transport = str(connection.get("transport", "tcp")).lower()
    timeout = float(connection.get("timeout", 3))

    if transport == "rtu":
        return ModbusSerialClient(
            port=connection.get("serial_port"),
            baudrate=int(connection.get("baudrate", 9600)),
            bytesize=int(connection.get("bytesize", 8)),
            parity=str(connection.get("parity", "N")),
            stopbits=int(connection.get("stopbits", 1)),
            timeout=timeout,
        )

    return ModbusTcpClient(
        connection.get("host", "127.0.0.1"),
        port=int(connection.get("port", 502)),
        timeout=timeout,
    )


def read_one(client, unit_id, name, field):
    area = str(field.get("area", "holding")).lower()
    addr = int(field["addr"])

    if area == "holding":
        response = client.read_holding_registers(addr, int(field.get("count", _count_for(field))), slave=unit_id)
        if response.isError():
            return None, f"{name}: {response}"
        return apply_enum(decode_registers(list(response.registers), field), field), None

    if area == "input":
        response = client.read_input_registers(addr, int(field.get("count", _count_for(field))), slave=unit_id)
        if response.isError():
            return None, f"{name}: {response}"
        return apply_enum(decode_registers(list(response.registers), field), field), None

    if area == "coil":
        response = client.read_coils(addr, 1, slave=unit_id)
        if response.isError():
            return None, f"{name}: {response}"
        return apply_enum(bool(response.bits[0]), field), None

    if area == "discrete":
        response = client.read_discrete_inputs(addr, 1, slave=unit_id)
        if response.isError():
            return None, f"{name}: {response}"
        return apply_enum(bool(response.bits[0]), field), None

    return None, f"{name}: unsupported area {area}"


def read_fields(connection, telemetry):
    client = make_client(connection)
    values = {}
    errors = []
    unit_id = int(connection.get("unit_id", connection.get("slave_id", 1)))

    if not client.connect():
        return values, ["modbus connect failed"]

    try:
        for name, field in telemetry.items():
            try:
                value, error = read_one(client, unit_id, name, field)
                if error:
                    errors.append(error)
                else:
                    values[name] = value
            except Exception as exc:
                errors.append(f"{name}: {exc}")
    finally:
        client.close()

    return values, errors


def write_field(connection, field, value):
    if str(field.get("area", "holding")).lower() != "holding":
        return False, "pilot EMS only writes holding registers"

    client = make_client(connection)
    unit_id = int(connection.get("unit_id", connection.get("slave_id", 1)))
    addr = int(field["addr"])
    words = [int(item) for item in field["values"]] if "values" in field else encode_words(field.get("fixed_value", value), field)

    if not client.connect():
        return False, "modbus connect failed"

    try:
        if len(words) == 1:
            response = client.write_register(addr, words[0], slave=unit_id)
        else:
            response = client.write_registers(addr, words, slave=unit_id)
        if response.isError():
            return False, str(response)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
    finally:
        client.close()
