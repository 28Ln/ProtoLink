from protolink.catalog import build_module_catalog
from protolink.core.models import ModuleStatus


def test_catalog_contains_foundation_and_transport_modules() -> None:
    modules = build_module_catalog()
    keys = {module.key for module in modules}
    names = {module.name for module in modules}

    assert "dashboard" in keys
    assert "serial_studio" in keys
    assert "modbus_rtu_lab" in keys
    assert "工作台总览" in names
    assert "串口工作台" in names
    assert "Modbus RTU 调试台" in names


def test_catalog_is_large_enough_for_platform_scope() -> None:
    modules = build_module_catalog()
    assert len(modules) >= 10


def test_catalog_marks_implemented_transport_surfaces_as_bootstrapped() -> None:
    modules = {module.key: module for module in build_module_catalog()}

    for key in (
        "serial_studio",
        "modbus_rtu_lab",
        "mqtt_client",
        "mqtt_server",
        "tcp_client",
        "tcp_server",
        "udp_lab",
    ):
        assert modules[key].status == ModuleStatus.BOOTSTRAPPED
