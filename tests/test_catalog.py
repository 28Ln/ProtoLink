from protolink.catalog import build_module_catalog
from protolink.core.models import ModuleStatus


def test_catalog_contains_foundation_and_transport_modules() -> None:
    modules = build_module_catalog()
    names = {module.name for module in modules}

    assert "Dashboard" in names
    assert "Serial Studio" in names
    assert "Modbus RTU Lab" in names


def test_catalog_is_large_enough_for_platform_scope() -> None:
    modules = build_module_catalog()
    assert len(modules) >= 10


def test_catalog_marks_implemented_transport_surfaces_as_bootstrapped() -> None:
    modules = {module.name: module for module in build_module_catalog()}

    for name in (
        "Serial Studio",
        "Modbus RTU Lab",
        "MQTT Client",
        "MQTT Server",
        "TCP Client",
        "TCP Server",
        "UDP Lab",
    ):
        assert modules[name].status == ModuleStatus.BOOTSTRAPPED
