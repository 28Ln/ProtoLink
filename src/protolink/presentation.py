from __future__ import annotations

from protolink.core.models import ModuleStatus
from protolink.core.transport import ConnectionState, TransportKind


APPLICATION_TITLE = "ProtoLink 工业通信工作台"
APPLICATION_SUBTITLE = "面向 Windows 的连接调试、协议分析与自动化协同平台"
HEADLESS_GOAL = "面向 Windows 的连接调试、协议分析与自动化协同平台"

MODULE_DISPLAY_NAMES = {
    "dashboard": "工作台总览",
    "serial_studio": "串口工作台",
    "modbus_rtu_lab": "Modbus RTU 调试台",
    "modbus_tcp_lab": "Modbus TCP 调试台",
    "mqtt_client": "MQTT 客户端",
    "mqtt_server": "MQTT 服务端",
    "tcp_client": "TCP 客户端",
    "tcp_server": "TCP 服务端",
    "udp_lab": "UDP 工作台",
    "packet_inspector": "报文分析台",
    "register_monitor": "寄存器监视",
    "automation_rules": "自动化规则",
    "script_console": "脚本控制台",
    "data_tools": "数据工具",
    "network_tools": "网络诊断",
    "Dashboard": "工作台总览",
    "Serial Studio": "串口工作台",
    "Modbus RTU Lab": "Modbus RTU 调试台",
    "Modbus TCP Lab": "Modbus TCP 调试台",
    "MQTT Client": "MQTT 客户端",
    "MQTT Server": "MQTT 服务端",
    "TCP Client": "TCP 客户端",
    "TCP Server": "TCP 服务端",
    "UDP Lab": "UDP 工作台",
    "Packet Inspector": "报文分析台",
    "Register Monitor": "寄存器监视",
    "Automation Rules": "自动化规则",
    "Script Console": "脚本控制台",
    "Data Tools": "数据工具",
    "Network Tools": "网络诊断",
}

AREA_DISPLAY_NAMES = {
    "Foundation": "基础底座",
    "Transport": "传输链路",
    "Protocol": "协议调试",
    "Shared": "共享能力",
    "Automation": "自动化",
    "Ops": "运维诊断",
    "基础底座": "基础底座",
    "传输链路": "传输链路",
    "协议调试": "协议调试",
    "共享能力": "共享能力",
    "自动化": "自动化",
    "运维诊断": "运维诊断",
}

STATUS_DISPLAY_NAMES = {
    ModuleStatus.BOOTSTRAPPED: "已就绪",
    ModuleStatus.NEXT: "开发中",
    ModuleStatus.PLANNED: "计划中",
}

CONNECTION_STATE_DISPLAY_NAMES = {
    ConnectionState.DISCONNECTED: "未连接",
    ConnectionState.CONNECTING: "连接中",
    ConnectionState.CONNECTED: "已连接",
    ConnectionState.STOPPING: "关闭中",
    ConnectionState.ERROR: "异常",
}

TRANSPORT_DISPLAY_NAMES = {
    TransportKind.SERIAL: "串口工作台",
    TransportKind.TCP_CLIENT: "TCP 客户端",
    TransportKind.TCP_SERVER: "TCP 服务端",
    TransportKind.UDP: "UDP 工作台",
    TransportKind.MQTT_CLIENT: "MQTT 客户端",
    TransportKind.MQTT_SERVER: "MQTT 服务端",
    "serial": "串口工作台",
    "tcp_client": "TCP 客户端",
    "tcp_server": "TCP 服务端",
    "udp": "UDP 工作台",
    "mqtt_client": "MQTT 客户端",
    "mqtt_server": "MQTT 服务端",
}


def display_module_name(name: str) -> str:
    return MODULE_DISPLAY_NAMES.get(name, name)


def display_module_area(area: str) -> str:
    return AREA_DISPLAY_NAMES.get(area, area)


def display_module_status(status: ModuleStatus) -> str:
    return STATUS_DISPLAY_NAMES.get(status, status.value)


def display_connection_state(state: ConnectionState | str) -> str:
    if isinstance(state, ConnectionState):
        return CONNECTION_STATE_DISPLAY_NAMES.get(state, state.value)
    try:
        return CONNECTION_STATE_DISPLAY_NAMES[ConnectionState(str(state))]
    except (KeyError, ValueError):
        return str(state)


def display_transport_name(kind: TransportKind | str) -> str:
    if isinstance(kind, TransportKind):
        return TRANSPORT_DISPLAY_NAMES.get(kind, kind.value)
    try:
        normalized = TransportKind(str(kind))
    except ValueError:
        return TRANSPORT_DISPLAY_NAMES.get(str(kind), str(kind))
    return TRANSPORT_DISPLAY_NAMES.get(normalized, normalized.value)
