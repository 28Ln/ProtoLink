from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.modbus_rtu_parser import crc16_modbus
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType
from protolink.ui.register_monitor_panel import RegisterMonitorPanel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_register_monitor_panel_can_save_decode_and_delete_points(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = RegisterMonitorPanel(context.register_monitor_service)

    panel.name_input.setText("Flow")
    panel.address_input.setValue(300)
    panel.data_type_combo.setCurrentIndex(panel.data_type_combo.findData(RegisterDataType.FLOAT32))
    panel.byte_order_combo.setCurrentIndex(panel.byte_order_combo.findData(RegisterByteOrder.CDAB))
    panel.scale_input.setText("1.0")
    panel.offset_input.setText("0.0")
    panel.unit_input.setText("L/s")
    panel.upsert_button.click()
    qapp.processEvents()

    assert context.register_monitor_service.snapshot.point_names == ("Flow",)
    assert panel.point_combo.count() == 2

    panel.register_words_input.setText("0x0000 0x3FC0")
    panel.decode_button.click()
    qapp.processEvents()

    assert "1.5 L/s" in panel.decoded_value_label.text()

    panel.delete_button.click()
    qapp.processEvents()

    assert context.register_monitor_service.snapshot.point_names == ()
    panel.close()


def test_register_monitor_panel_reflects_live_modbus_source(qapp: QApplication, tmp_path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    panel = RegisterMonitorPanel(context.register_monitor_service)

    panel.name_input.setText("Holding")
    panel.address_input.setValue(1)
    panel.data_type_combo.setCurrentIndex(panel.data_type_combo.findData(RegisterDataType.UINT16))
    panel.byte_order_combo.setCurrentIndex(panel.byte_order_combo.findData(RegisterByteOrder.AB))
    panel.unit_input.setText("rpm")
    panel.upsert_button.click()
    qapp.processEvents()

    body = bytes([0x01, 0x03, 0x02, 0x00, 0x2A])
    context.event_bus.publish(
        create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message="Inbound payload (7 bytes)",
            raw_payload=body + crc16_modbus(body).to_bytes(2, "little"),
        )
    )
    qapp.processEvents()

    assert "Source: modbus_rtu" in panel.status_label.text()
    assert "42 rpm" in panel.decoded_value_label.text()
    panel.close()
