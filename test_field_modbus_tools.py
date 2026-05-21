import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_tool(name):
    path = ROOT / "field_tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doctor_parses_unit_ranges():
    doctor = load_tool("field_modbus_doctor")

    assert doctor.parse_unit_range("1-3,7,10-11") == [1, 2, 3, 7, 10, 11]


def test_read_table_decodes_u32_word_order():
    read_table = load_tool("field_modbus_read_table")

    assert read_table.decode_registers([0x0001, 0x0002], "u32", word_order="big") == 65538
    assert read_table.decode_registers([0x0001, 0x0002], "u32", word_order="little") == 131073


def test_read_table_suggests_common_base_address_candidates():
    read_table = load_tool("field_modbus_read_table")

    assert read_table.build_address_candidates(40001, probe_offsets=True) == [0, 1, 40000, 40001, 40002]
    assert read_table.build_address_candidates(30001, probe_offsets=True) == [0, 1, 30000, 30001, 30002]


def test_safe_write_parses_register_values():
    safe_write = load_tool("field_modbus_safe_write")

    assert safe_write.parse_number("0x10") == 16
    assert safe_write.parse_write_values("1, 0x02, 3") == [1, 2, 3]
    assert safe_write.encode_single_value(-1, "i16", scale=1) == 0xFFFF
