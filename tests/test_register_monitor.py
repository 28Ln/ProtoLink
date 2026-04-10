import math

from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType, RegisterPoint, decode_register_point


def test_register_monitor_decodes_uint16_with_scale_and_offset() -> None:
    point = RegisterPoint(
        name="Temperature",
        address=100,
        data_type=RegisterDataType.UINT16,
        scale=0.1,
        offset=2.0,
    )

    decoded = decode_register_point(point, [123])

    assert math.isclose(decoded, 14.3, rel_tol=0.0, abs_tol=1e-6)


def test_register_monitor_decodes_uint16_with_byte_swap() -> None:
    point = RegisterPoint(
        name="WordSwap16",
        address=120,
        data_type=RegisterDataType.UINT16,
        byte_order=RegisterByteOrder.BA,
    )

    decoded = decode_register_point(point, [0x3412])

    assert decoded == 0x1234


def test_register_monitor_decodes_int32_and_float32() -> None:
    int_point = RegisterPoint(
        name="SignedCounter",
        address=200,
        data_type=RegisterDataType.INT32,
        byte_order=RegisterByteOrder.AB,
    )
    float_point = RegisterPoint(
        name="Flow",
        address=300,
        data_type=RegisterDataType.FLOAT32,
        byte_order=RegisterByteOrder.CDAB,
    )

    int_value = decode_register_point(int_point, [0xFFFF, 0xFFD6])  # -42
    float_value = decode_register_point(float_point, [0x0000, 0x3FC0])  # word-swapped 1.5

    assert int_value == -42
    assert math.isclose(float_value, 1.5, rel_tol=0.0, abs_tol=1e-6)


def test_register_monitor_rejects_invalid_register_inputs() -> None:
    point = RegisterPoint(name="NeedTwoRegs", address=10, data_type=RegisterDataType.UINT32)

    try:
        decode_register_point(point, [0x0001])
    except ValueError as exc:
        assert "requires 2 register(s)" in str(exc)
    else:
        raise AssertionError("Expected ValueError for too few registers.")

    try:
        decode_register_point(point, [0x0001, 0x10000])
    except ValueError as exc:
        assert "16-bit unsigned values" in str(exc)
    else:
        raise AssertionError("Expected ValueError for out-of-range register.")
