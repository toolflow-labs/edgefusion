def test_decode_registers_handles_signed_scaled_i32():
    from pilot_ems.io_modbus import decode_registers

    assert decode_registers([0xFFFF, 0xFF9C], {"type": "i32", "scale": 0.1}) == -10


def test_decode_registers_handles_little_word_order():
    from pilot_ems.io_modbus import decode_registers

    assert decode_registers([0x0001, 0x0002], {"type": "u32", "word_order": "little"}) == 131073


def test_encode_words_handles_i16_negative_value():
    from pilot_ems.io_modbus import encode_words

    assert encode_words(-1, {"type": "i16"}) == [0xFFFF]
