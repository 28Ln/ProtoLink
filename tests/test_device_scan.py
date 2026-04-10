from protolink.core.device_scan import (
    DeviceScanConfig,
    DeviceScanOutcome,
    DeviceScanTransportKind,
    build_device_scan_requests,
    build_device_scan_summary,
    evaluate_device_scan_response,
)
from protolink.core.modbus_rtu_parser import crc16_modbus


def test_device_scan_builds_modbus_rtu_requests_with_crc() -> None:
    config = DeviceScanConfig(
        transport_kind=DeviceScanTransportKind.MODBUS_RTU,
        target="COM7@115200",
        unit_id_start=1,
        unit_id_end=3,
        start_address=0x0010,
        quantity=1,
    )

    requests = build_device_scan_requests(config)

    assert len(requests) == 3
    assert requests[0].unit_id == 1
    assert requests[0].payload[0] == 1
    assert requests[2].payload[0] == 3
    for request in requests:
        frame_without_crc = request.payload[:-2]
        assert request.payload[-2:] == crc16_modbus(frame_without_crc).to_bytes(2, "little")


def test_device_scan_builds_modbus_tcp_requests_with_transaction_ids() -> None:
    config = DeviceScanConfig(
        transport_kind=DeviceScanTransportKind.MODBUS_TCP,
        target="127.0.0.1:502",
        unit_id_start=2,
        unit_id_end=4,
        start_address=0x000A,
        quantity=2,
    )

    requests = build_device_scan_requests(config)

    assert len(requests) == 3
    assert requests[0].payload[0:2] == b"\x00\x01"
    assert requests[1].payload[0:2] == b"\x00\x02"
    assert requests[0].payload[6] == 2
    assert requests[2].payload[6] == 4


def test_device_scan_evaluates_rtu_and_tcp_responses_and_summarizes() -> None:
    rtu_body = bytes([0x01, 0x03, 0x02, 0x00, 0x2A])
    rtu_ok = rtu_body + crc16_modbus(rtu_body).to_bytes(2, "little")
    rtu_exc_body = bytes([0x02, 0x83, 0x02])
    rtu_exc = rtu_exc_body + crc16_modbus(rtu_exc_body).to_bytes(2, "little")

    tcp_ok = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x05, 0x03, 0x03, 0x02, 0x00, 0x2A])
    tcp_exc = bytes([0x00, 0x02, 0x00, 0x00, 0x00, 0x03, 0x04, 0x83, 0x02])

    rtu_outcome_ok = evaluate_device_scan_response(
        DeviceScanTransportKind.MODBUS_RTU,
        expected_unit_id=1,
        payload=rtu_ok,
    )
    rtu_outcome_exc = evaluate_device_scan_response(
        DeviceScanTransportKind.MODBUS_RTU,
        expected_unit_id=2,
        payload=rtu_exc,
    )
    tcp_outcome_ok = evaluate_device_scan_response(
        DeviceScanTransportKind.MODBUS_TCP,
        expected_unit_id=3,
        payload=tcp_ok,
    )
    tcp_outcome_exc = evaluate_device_scan_response(
        DeviceScanTransportKind.MODBUS_TCP,
        expected_unit_id=4,
        payload=tcp_exc,
    )

    assert rtu_outcome_ok.reachable is True
    assert rtu_outcome_exc.exception_code == 0x02
    assert tcp_outcome_ok.reachable is True
    assert tcp_outcome_exc.exception_code == 0x02

    summary = build_device_scan_summary(
        DeviceScanConfig(
            transport_kind=DeviceScanTransportKind.MODBUS_TCP,
            target="127.0.0.1:502",
            unit_id_start=3,
            unit_id_end=5,
        ),
        outcomes=(
            tcp_outcome_ok,
            tcp_outcome_exc,
            DeviceScanOutcome(unit_id=5, reachable=False, error="No response within timeout."),
        ),
    )
    assert summary.discovered_units == (3,)
    assert summary.exception_units == (4,)
    assert summary.missing_units == (5,)
    assert "No response within timeout." in summary.errors
