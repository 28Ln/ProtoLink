from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESOLUTION_TOKENS = (
    "1180x760",
    "1366x768",
    "1480x920",
    "1680x1050",
)
DEFAULT_MODULE_KEYS = (
    "dashboard",
    "serial_studio",
    "mqtt_client",
    "tcp_server",
    "modbus_rtu_lab",
    "modbus_tcp_lab",
    "register_monitor",
    "automation_rules",
)
QT_PROPAGATE_SIZE_HINTS_WARNING = "This plugin does not support propagateSizeHints()"
SEVERITY_ORDER = {
    "clean": 0,
    "info": 1,
    "warn": 2,
    "error": 3,
}


class VerificationError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="离屏审计 ProtoLink GUI 的布局、几何、截图与溢出摘要。")
    parser.add_argument("--workspace", type=Path, help="可选，使用指定 workspace。默认创建临时 workspace。")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="审计产物输出目录。默认输出到 dist/gui-audit/<timestamp>。",
    )
    parser.add_argument(
        "--resolution",
        dest="resolutions",
        action="append",
        help="审计分辨率，格式 WIDTHxHEIGHT。可重复传入；默认内置 4 个验收分辨率。",
    )
    parser.add_argument(
        "--module",
        dest="module_keys",
        action="append",
        help="审计模块 key。可重复传入；默认使用关键模块集。",
    )
    parser.add_argument(
        "--all-modules",
        action="store_true",
        help="审计全部模块，而不是默认关键模块集。",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="保留自动创建的临时 workspace。",
    )
    return parser


def _parse_resolution(token: str) -> tuple[int, int]:
    normalized = token.strip().lower()
    if "x" not in normalized:
        raise VerificationError(f"Invalid resolution '{token}'. Expected WIDTHxHEIGHT.")
    width_text, height_text = normalized.split("x", maxsplit=1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError as exc:
        raise VerificationError(f"Invalid resolution '{token}'. Expected WIDTHxHEIGHT.") from exc
    if width <= 0 or height <= 0:
        raise VerificationError(f"Resolution '{token}' must be greater than zero.")
    return width, height


def _available_modules() -> list[dict[str, str]]:
    from protolink.catalog import build_module_catalog

    return [{"key": module.key, "name": module.name} for module in build_module_catalog()]


def _severity_max(*values: str) -> str:
    if not values:
        return "clean"
    return max(values, key=lambda item: SEVERITY_ORDER.get(item, 0))


def _normalize_resolutions(raw_tokens: list[str] | None) -> list[tuple[int, int]]:
    tokens = raw_tokens or list(DEFAULT_RESOLUTION_TOKENS)
    return [_parse_resolution(token) for token in tokens]


def _normalize_module_keys(raw_keys: list[str] | None, *, audit_all_modules: bool) -> list[str]:
    available_modules = _available_modules()
    available_by_key = {module["key"]: module["name"] for module in available_modules}
    module_keys = list(available_by_key.keys()) if audit_all_modules else list(raw_keys or DEFAULT_MODULE_KEYS)

    unknown_keys = [key for key in module_keys if key not in available_by_key]
    if unknown_keys:
        raise VerificationError(
            "Unknown module key(s): "
            + ", ".join(sorted(unknown_keys))
            + ". Available keys: "
            + ", ".join(sorted(available_by_key))
        )

    deduplicated: list[str] = []
    for key in module_keys:
        if key not in deduplicated:
            deduplicated.append(key)
    return deduplicated


def _default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ROOT / "dist" / "gui-audit" / stamp


def _configure_qt_environment() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if os.name == "nt" and "QT_QPA_FONTDIR" not in os.environ:
        windows_root = Path(os.environ.get("WINDIR", r"C:\Windows"))
        font_dir = windows_root / "Fonts"
        if font_dir.exists():
            os.environ["QT_QPA_FONTDIR"] = str(font_dir)


def _create_qapplication():
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    from protolink.ui.theme import APP_STYLESHEET

    previous_qt_message_handler = None

    def handle_qt_message(mode, context, message) -> None:
        if message == QT_PROPAGATE_SIZE_HINTS_WARNING:
            return
        if previous_qt_message_handler is not None:
            previous_qt_message_handler(mode, context, message)

    previous_qt_message_handler = qInstallMessageHandler(handle_qt_message)
    app = QApplication.instance()
    created = app is None
    if app is None:
        app = QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    return app, created, previous_qt_message_handler, qInstallMessageHandler


def _build_context_and_window(workspace: Path):
    from protolink.core.bootstrap import bootstrap_app_context
    from protolink.ui.main_window import ProtoLinkMainWindow
    from protolink.ui.qt_dispatch import QtCallbackDispatcher

    base_dir = workspace.parent if workspace.parent != workspace else workspace
    context = bootstrap_app_context(
        base_dir,
        workspace_override=workspace,
        persist_settings=False,
        remember_workspace_override=False,
    )
    dispatcher = QtCallbackDispatcher()
    context.serial_session_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.mqtt_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.mqtt_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.tcp_client_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.tcp_server_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.udp_service.set_dispatch_scheduler(dispatcher.dispatch)
    context.packet_replay_service.set_dispatch_scheduler(dispatcher.dispatch)
    window = ProtoLinkMainWindow(
        workspace=context.workspace,
        inspector=context.packet_inspector,
        data_tools_service=context.data_tools_service,
        network_tools_service=context.network_tools_service,
        serial_service=context.serial_session_service,
        mqtt_client_service=context.mqtt_client_service,
        mqtt_server_service=context.mqtt_server_service,
        tcp_client_service=context.tcp_client_service,
        tcp_server_service=context.tcp_server_service,
        udp_service=context.udp_service,
        packet_replay_service=context.packet_replay_service,
        register_monitor_service=context.register_monitor_service,
        rule_engine_service=context.rule_engine_service,
        auto_response_runtime_service=context.auto_response_runtime_service,
        script_console_service=context.script_console_service,
        timed_task_service=context.timed_task_service,
        channel_bridge_runtime_service=context.channel_bridge_runtime_service,
    )
    return context, window


def _shutdown_context(context) -> None:
    context.serial_session_service.shutdown()
    context.mqtt_client_service.shutdown()
    context.mqtt_server_service.shutdown()
    context.tcp_client_service.shutdown()
    context.tcp_server_service.shutdown()
    context.udp_service.shutdown()
    context.packet_replay_service.shutdown()
    context.timed_task_service.shutdown()
    context.channel_bridge_runtime_service.shutdown()


def _pump_events(app, *, cycles: int = 4) -> None:
    for _ in range(cycles):
        app.processEvents()
        app.sendPostedEvents()


def _rect_payload(rect) -> dict[str, int]:
    return {
        "x": int(rect.x()),
        "y": int(rect.y()),
        "width": int(rect.width()),
        "height": int(rect.height()),
    }


def _size_payload(size) -> dict[str, int]:
    return {
        "width": int(size.width()),
        "height": int(size.height()),
    }


def _widget_descriptor(widget) -> dict[str, object]:
    return {
        "class_name": widget.metaObject().className(),
        "object_name": widget.objectName() or "",
        "geometry": _rect_payload(widget.geometry()),
        "size": {"width": int(widget.width()), "height": int(widget.height())},
        "size_hint": _size_payload(widget.sizeHint()),
        "minimum_size_hint": _size_payload(widget.minimumSizeHint()),
        "visible": bool(widget.isVisible()),
    }


def _normalized_text(value: str) -> str:
    return " ".join(value.replace("&", "").split())


def _collect_text_pressure(root_widget) -> list[dict[str, object]]:
    from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

    examples: list[dict[str, object]] = []
    for widget in root_widget.findChildren(QWidget):
        if not widget.isVisible():
            continue
        if isinstance(widget, QLabel):
            text = _normalized_text(widget.text())
            if not text:
                continue
            available_width = max(1, int(widget.contentsRect().width()))
            available_height = max(1, int(widget.contentsRect().height()))
            if widget.wordWrap():
                required_height = widget.heightForWidth(available_width)
                if required_height <= 0:
                    required_height = widget.sizeHint().height()
                if required_height > available_height + 4:
                    examples.append(
                        {
                            "class_name": widget.metaObject().className(),
                            "object_name": widget.objectName() or "",
                            "text": text[:120],
                            "axis": "height",
                            "available": available_height,
                            "required": int(required_height),
                        }
                    )
                continue

            required_width = widget.fontMetrics().horizontalAdvance(text)
            if required_width > available_width + 12:
                examples.append(
                    {
                        "class_name": widget.metaObject().className(),
                        "object_name": widget.objectName() or "",
                        "text": text[:120],
                        "axis": "width",
                        "available": available_width,
                        "required": int(required_width),
                    }
                )
            continue

        if isinstance(widget, QAbstractButton):
            if widget.objectName() in {"WindowButton", "WindowCloseButton"}:
                continue
            text = _normalized_text(widget.text())
            if not text:
                continue
            available_width = max(1, int(widget.contentsRect().width()))
            required_width = widget.sizeHint().width()
            if required_width > available_width + 8:
                examples.append(
                    {
                        "class_name": widget.metaObject().className(),
                        "object_name": widget.objectName() or "",
                        "text": text[:120],
                        "axis": "width",
                        "available": available_width,
                        "required": int(required_width),
                    }
                )
    return examples


def _collect_tab_pressure(root_widget) -> list[dict[str, object]]:
    from PySide6.QtWidgets import QTabBar

    examples: list[dict[str, object]] = []
    for tab_bar in root_widget.findChildren(QTabBar):
        if not tab_bar.isVisible():
            continue
        for index in range(tab_bar.count()):
            tab_rect = tab_bar.tabRect(index)
            tab_hint = tab_bar.tabSizeHint(index)
            if tab_hint.width() > tab_rect.width() + 6:
                examples.append(
                    {
                        "object_name": tab_bar.objectName() or "",
                        "tab_text": tab_bar.tabText(index),
                        "available_width": int(tab_rect.width()),
                        "required_width": int(tab_hint.width()),
                    }
                )
    return examples


def _collect_scroll_areas(root_widget) -> list[dict[str, object]]:
    from PySide6.QtWidgets import QAbstractScrollArea, QScrollArea

    scroll_areas: list[dict[str, object]] = []
    for area in root_widget.findChildren(QAbstractScrollArea):
        if not area.isVisible():
            continue
        vertical_maximum = int(area.verticalScrollBar().maximum())
        horizontal_maximum = int(area.horizontalScrollBar().maximum())
        if vertical_maximum <= 0 and horizontal_maximum <= 0 and not isinstance(area, QScrollArea):
            continue
        payload = _widget_descriptor(area)
        payload.update(
            {
                "vertical_scroll_maximum": vertical_maximum,
                "horizontal_scroll_maximum": horizontal_maximum,
                "viewport": _rect_payload(area.viewport().geometry()),
            }
        )
        if isinstance(area, QScrollArea) and area.widget() is not None:
            payload["content_widget"] = _widget_descriptor(area.widget())
        scroll_areas.append(payload)
    return scroll_areas


def _collect_visible_tabs(root_widget) -> list[dict[str, object]]:
    from PySide6.QtWidgets import QTabWidget

    tab_groups: list[dict[str, object]] = []
    for tab_widget in root_widget.findChildren(QTabWidget):
        if not tab_widget.isVisible():
            continue
        tab_groups.append(
            {
                "object_name": tab_widget.objectName() or "",
                "tab_count": int(tab_widget.count()),
                "current_index": int(tab_widget.currentIndex()),
                "current_tab": tab_widget.tabText(tab_widget.currentIndex()) if tab_widget.count() else "",
                "tabs": [tab_widget.tabText(index) for index in range(tab_widget.count())],
                "geometry": _rect_payload(tab_widget.geometry()),
            }
        )
    return tab_groups


def _collect_visible_splitters(root_widget) -> list[dict[str, object]]:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter

    splitters: list[dict[str, object]] = []
    for splitter in root_widget.findChildren(QSplitter):
        if not splitter.isVisible():
            continue
        splitters.append(
            {
                "object_name": splitter.objectName() or "",
                "orientation": "horizontal"
                if splitter.orientation() == Qt.Orientation.Horizontal
                else "vertical",
                "sizes": [int(size) for size in splitter.sizes()],
                "geometry": _rect_payload(splitter.geometry()),
            }
        )
    return splitters


def _collect_window_metrics(window) -> tuple[dict[str, object], list[dict[str, object]]]:
    from PySide6.QtWidgets import QWidget

    hero = window.findChild(QWidget, "Hero")
    sidebar = window.findChild(QWidget, "Sidebar")
    metrics = {
        "window": {
            "width": int(window.width()),
            "height": int(window.height()),
        },
        "panel_stack_height": int(window.panel_stack.height()),
        "panel_stack_width": int(window.panel_stack.width()),
        "packet_console_dock_height": int(window.packet_console_dock.height()),
        "packet_console_dock_width": int(window.packet_console_dock.width()),
        "module_context_visible": bool(window.module_context_surface.isVisible()),
        "module_context_width": int(window.module_context_surface.width()) if window.module_context_surface.isVisible() else 0,
        "content_splitter_sizes": [int(size) for size in window.content_splitter.sizes()],
        "hero_height": int(hero.height()) if hero is not None else None,
        "sidebar_width": int(sidebar.width()) if sidebar is not None else None,
    }

    issues: list[dict[str, object]] = []
    if metrics["panel_stack_height"] < 220:
        issues.append(
            {
                "severity": "error",
                "kind": "panel_stack_too_small",
                "detail": f"panel_stack_height={metrics['panel_stack_height']}",
            }
        )
    if metrics["packet_console_dock_height"] > max(140, int(window.height() * 0.24)):
        issues.append(
            {
                "severity": "warn",
                "kind": "packet_console_dock_too_tall",
                "detail": f"dock_height={metrics['packet_console_dock_height']}",
            }
        )
    if window.width() <= 1366 and metrics["module_context_visible"]:
        issues.append(
            {
                "severity": "warn",
                "kind": "module_context_not_collapsed",
                "detail": f"module_context_width={metrics['module_context_width']}",
            }
        )
    return metrics, issues


def _capture_widget_image(widget, target_file: Path) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(target_file), "PNG"):
        raise VerificationError(f"Failed to save screenshot: {target_file}")


def _build_panel_payload(window) -> tuple[object, object, dict[str, object]]:
    from PySide6.QtWidgets import QScrollArea

    wrapper = window.panel_stack.currentWidget()
    if wrapper is None:
        raise VerificationError("Panel stack has no active widget.")
    panel_root = wrapper.widget() if isinstance(wrapper, QScrollArea) and wrapper.widget() is not None else wrapper
    payload = {
        "wrapper": _widget_descriptor(wrapper),
        "root": _widget_descriptor(panel_root),
    }
    if isinstance(wrapper, QScrollArea):
        payload["viewport"] = _rect_payload(wrapper.viewport().geometry())
        payload["scrollbars"] = {
            "vertical_maximum": int(wrapper.verticalScrollBar().maximum()),
            "horizontal_maximum": int(wrapper.horizontalScrollBar().maximum()),
        }
    return wrapper, panel_root, payload


def _collect_overflow_summary(root_widget, *, viewport_height: int | None = None) -> dict[str, object]:
    scroll_areas = _collect_scroll_areas(root_widget)
    text_pressure = _collect_text_pressure(root_widget)
    tab_pressure = _collect_tab_pressure(root_widget)

    issues: list[dict[str, object]] = []
    horizontal_scroll_area_count = sum(1 for item in scroll_areas if item["horizontal_scroll_maximum"] > 0)
    vertical_scroll_area_count = sum(1 for item in scroll_areas if item["vertical_scroll_maximum"] > 0)

    for item in scroll_areas:
        if item["horizontal_scroll_maximum"] > 0:
            issues.append(
                {
                    "severity": "error",
                    "kind": "horizontal_scroll_active",
                    "object_name": item["object_name"],
                    "class_name": item["class_name"],
                    "horizontal_scroll_maximum": item["horizontal_scroll_maximum"],
                }
            )

    for item in text_pressure:
        issues.append(
            {
                "severity": "warn",
                "kind": "text_pressure",
                **item,
            }
        )

    for item in tab_pressure:
        issues.append(
            {
                "severity": "warn",
                "kind": "tab_pressure",
                **item,
            }
        )

    if viewport_height is not None and viewport_height < 180:
        issues.append(
            {
                "severity": "warn",
                "kind": "viewport_too_short",
                "detail": f"viewport_height={viewport_height}",
            }
        )

    highest_severity = _severity_max(*(issue["severity"] for issue in issues))
    return {
        "severity": highest_severity,
        "issue_count": len(issues),
        "vertical_scroll_area_count": vertical_scroll_area_count,
        "horizontal_scroll_area_count": horizontal_scroll_area_count,
        "scroll_areas": scroll_areas,
        "text_pressure_count": len(text_pressure),
        "text_pressure_examples": text_pressure[:20],
        "tab_pressure_count": len(tab_pressure),
        "tab_pressure_examples": tab_pressure[:20],
        "issues": issues[:30],
    }


def _merge_wrapper_scroll_metrics(
    overflow_summary: dict[str, object],
    *,
    wrapper_descriptor: dict[str, object],
    viewport_descriptor: dict[str, int],
    scrollbars: dict[str, int],
) -> dict[str, object]:
    wrapper_payload = dict(wrapper_descriptor)
    wrapper_payload.update(
        {
            "viewport": viewport_descriptor,
            "vertical_scroll_maximum": int(scrollbars.get("vertical_maximum", 0)),
            "horizontal_scroll_maximum": int(scrollbars.get("horizontal_maximum", 0)),
        }
    )
    scroll_areas = list(overflow_summary.get("scroll_areas", []))
    scroll_areas.insert(0, wrapper_payload)
    overflow_summary["scroll_areas"] = scroll_areas
    overflow_summary["wrapper_scroll_area"] = wrapper_payload
    if wrapper_payload["vertical_scroll_maximum"] > 0:
        overflow_summary["vertical_scroll_area_count"] = int(overflow_summary["vertical_scroll_area_count"]) + 1
    if wrapper_payload["horizontal_scroll_maximum"] > 0:
        overflow_summary["horizontal_scroll_area_count"] = int(overflow_summary["horizontal_scroll_area_count"]) + 1
        issues = list(overflow_summary.get("issues", []))
        issues.insert(
            0,
            {
                "severity": "error",
                "kind": "horizontal_scroll_active",
                "object_name": wrapper_payload["object_name"],
                "class_name": wrapper_payload["class_name"],
                "horizontal_scroll_maximum": wrapper_payload["horizontal_scroll_maximum"],
            },
        )
        overflow_summary["issues"] = issues[:30]
        overflow_summary["issue_count"] = int(overflow_summary["issue_count"]) + 1
        overflow_summary["severity"] = _severity_max(str(overflow_summary["severity"]), "error")
    return overflow_summary


def _select_module(window, module_key: str, app) -> dict[str, str]:
    available_by_key = {module.key: module.name for module in window.modules}
    if module_key not in available_by_key:
        raise VerificationError(f"Module key '{module_key}' is not available in the main window.")
    module_index = next(index for index, module in enumerate(window.modules) if module.key == module_key)
    if window.module_list.currentRow() != module_index:
        window.module_list.setCurrentRow(module_index)
    _pump_events(app)
    return {"key": module_key, "name": available_by_key[module_key]}


def _audit_packet_console(window, *, screenshot_dir: Path, resolution_label: str) -> dict[str, object]:
    screenshot_file = screenshot_dir / resolution_label / "packet-console.png"
    _capture_widget_image(window.packet_console_dock, screenshot_file)
    root_widget = window.packet_console
    overflow_summary = _collect_overflow_summary(root_widget)
    wrapper_scroll = getattr(window, "packet_console_scroll", None)
    if wrapper_scroll is not None:
        overflow_summary = _merge_wrapper_scroll_metrics(
            overflow_summary,
            wrapper_descriptor=_widget_descriptor(wrapper_scroll),
            viewport_descriptor=_rect_payload(wrapper_scroll.viewport().geometry()),
            scrollbars={
                "vertical_maximum": int(wrapper_scroll.verticalScrollBar().maximum()),
                "horizontal_maximum": int(wrapper_scroll.horizontalScrollBar().maximum()),
            },
        )
    return {
        "screenshot_file": str(screenshot_file.resolve()),
        "widget": _widget_descriptor(window.packet_console_dock),
        "packet_console_widget": _widget_descriptor(root_widget),
        "tabs": _collect_visible_tabs(root_widget),
        "splitters": _collect_visible_splitters(root_widget),
        "overflow_summary": overflow_summary,
    }


def _audit_module(window, module_key: str, *, screenshot_dir: Path, resolution_label: str, app) -> dict[str, object]:
    module = _select_module(window, module_key, app)
    wrapper, panel_root, panel_payload = _build_panel_payload(window)
    viewport_height = panel_payload.get("viewport", {}).get("height") if isinstance(panel_payload.get("viewport"), dict) else None
    overflow_summary = _collect_overflow_summary(panel_root, viewport_height=viewport_height)
    if "scrollbars" in panel_payload and "viewport" in panel_payload:
        overflow_summary = _merge_wrapper_scroll_metrics(
            overflow_summary,
            wrapper_descriptor=panel_payload["wrapper"],
            viewport_descriptor=panel_payload["viewport"],
            scrollbars=panel_payload["scrollbars"],
        )
    window_file = screenshot_dir / resolution_label / f"{module_key}-window.png"
    panel_file = screenshot_dir / resolution_label / f"{module_key}-panel.png"
    _capture_widget_image(window, window_file)
    _capture_widget_image(wrapper, panel_file)
    return {
        "module_key": module["key"],
        "module_name": module["name"],
        "screenshots": {
            "window": str(window_file.resolve()),
            "panel": str(panel_file.resolve()),
        },
        "panel": panel_payload,
        "tabs": _collect_visible_tabs(panel_root),
        "splitters": _collect_visible_splitters(panel_root),
        "overflow_summary": overflow_summary,
    }


def _audit_resolution(
    workspace: Path,
    *,
    output_dir: Path,
    resolution: tuple[int, int],
    module_keys: list[str],
    app,
) -> dict[str, object]:
    context, window = _build_context_and_window(workspace)
    width, height = resolution
    resolution_label = f"{width}x{height}"
    screenshot_dir = output_dir / "screenshots"
    try:
        window.resize(width, height)
        window.show()
        _pump_events(app, cycles=6)

        window_metrics, window_issues = _collect_window_metrics(window)
        packet_console = _audit_packet_console(window, screenshot_dir=screenshot_dir, resolution_label=resolution_label)
        module_results = [
            _audit_module(window, module_key, screenshot_dir=screenshot_dir, resolution_label=resolution_label, app=app)
            for module_key in module_keys
        ]
        resolution_severity = _severity_max(
            *(issue["severity"] for issue in window_issues),
            packet_console["overflow_summary"]["severity"],
            *(item["overflow_summary"]["severity"] for item in module_results),
        )
        return {
            "resolution": {"width": width, "height": height, "label": resolution_label},
            "window_metrics": window_metrics,
            "window_issues": window_issues,
            "packet_console": packet_console,
            "module_results": module_results,
            "severity": resolution_severity,
        }
    finally:
        window.close()
        _pump_events(app)
        _shutdown_context(context)


def _summarize_results(resolution_results: list[dict[str, object]]) -> dict[str, object]:
    severity_counts = {name: 0 for name in SEVERITY_ORDER}
    flagged_targets: list[dict[str, object]] = []
    screenshot_count = 0
    highest = "clean"

    for resolution_result in resolution_results:
        highest = _severity_max(highest, str(resolution_result["severity"]))
        severity_counts[str(resolution_result["severity"])] += 1
        screenshot_count += 1  # packet console
        if resolution_result["severity"] != "clean":
            flagged_targets.append(
                {
                    "scope": "resolution",
                    "resolution": resolution_result["resolution"]["label"],
                    "severity": resolution_result["severity"],
                }
            )

        packet_console_severity = resolution_result["packet_console"]["overflow_summary"]["severity"]
        highest = _severity_max(highest, packet_console_severity)
        severity_counts[packet_console_severity] += 1
        if packet_console_severity != "clean":
            flagged_targets.append(
                {
                    "scope": "packet_console",
                    "resolution": resolution_result["resolution"]["label"],
                    "severity": packet_console_severity,
                }
            )

        for module_result in resolution_result["module_results"]:
            screenshot_count += len(module_result["screenshots"])
            module_severity = module_result["overflow_summary"]["severity"]
            highest = _severity_max(highest, module_severity)
            if module_severity != "clean":
                flagged_targets.append(
                    {
                        "scope": "module",
                        "resolution": resolution_result["resolution"]["label"],
                        "module_key": module_result["module_key"],
                        "module_name": module_result["module_name"],
                        "severity": module_severity,
                    }
                )
            severity_counts[module_severity] += 1

    return {
        "resolution_count": len(resolution_results),
        "module_audit_count": sum(len(item["module_results"]) for item in resolution_results),
        "screenshot_count": screenshot_count,
        "severity_counts": severity_counts,
        "highest_severity": highest,
        "flagged_targets": flagged_targets,
    }


def execute_gui_layout_audit(
    *,
    workspace: Path | None = None,
    output_dir: Path | None = None,
    resolutions: list[tuple[int, int]] | None = None,
    module_keys: list[str] | None = None,
    audit_all_modules: bool = False,
    keep_artifacts: bool = False,
) -> dict[str, object]:
    temp_root: Path | None = None
    if workspace is None:
        temp_root = Path(tempfile.mkdtemp(prefix="protolink-gui-audit-"))
        workspace = temp_root / "workspace"
    workspace = workspace.resolve()
    output_dir = (output_dir or _default_output_dir()).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = output_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    json_file = output_dir / "gui-layout-audit.json"

    normalized_resolutions = resolutions or _normalize_resolutions(None)
    normalized_module_keys = _normalize_module_keys(module_keys, audit_all_modules=audit_all_modules)

    _configure_qt_environment()
    app, created_app, previous_handler, install_handler = _create_qapplication()
    started_at = time.perf_counter()
    temporary_workspace_removed = False
    result: dict[str, object] | None = None
    try:
        resolution_results = [
            _audit_resolution(
                workspace,
                output_dir=output_dir,
                resolution=resolution,
                module_keys=normalized_module_keys,
                app=app,
            )
            for resolution in normalized_resolutions
        ]
        result = {
            "workspace": str(workspace),
            "temporary_root": str(temp_root) if temp_root is not None else None,
            "temporary_workspace_removed": False,
            "output_dir": str(output_dir),
            "json_file": str(json_file),
            "screenshot_dir": str(screenshot_dir),
            "available_modules": _available_modules(),
            "requested_modules": normalized_module_keys,
            "requested_resolutions": [
                {"width": width, "height": height, "label": f"{width}x{height}"}
                for width, height in normalized_resolutions
            ],
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
            "summary": _summarize_results(resolution_results),
            "resolution_results": resolution_results,
        }
        json_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    finally:
        if created_app:
            app.quit()
        install_handler(previous_handler)
        if temp_root is not None and not keep_artifacts:
            shutil.rmtree(temp_root, ignore_errors=True)
            temporary_workspace_removed = True
        if temporary_workspace_removed:
            if result is not None:
                result["temporary_workspace_removed"] = True
            if json_file.exists():
                payload = json.loads(json_file.read_text(encoding="utf-8"))
                payload["temporary_workspace_removed"] = True
                json_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    resolutions = _normalize_resolutions(args.resolutions)
    result = execute_gui_layout_audit(
        workspace=args.workspace,
        output_dir=args.output_dir,
        resolutions=resolutions,
        module_keys=args.module_keys,
        audit_all_modules=args.all_modules,
        keep_artifacts=args.keep_artifacts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
