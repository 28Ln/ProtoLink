from __future__ import annotations

from protolink.core.logging import LogLevel
from protolink.core.models import ModuleStatus
from protolink.core.packet_inspector import PayloadViewMode
from protolink.core.raw_packet_composer import RawPacketInputMode, RawPacketLineEnding
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType
from protolink.core.script_host import ScriptLanguage
from protolink.core.transport import ConnectionState, TransportKind


READY_TEXT = "等待操作"
CURRENT_DRAFT_TEXT = "未保存配置"
DRAFT_TEXT = "编辑内容"
NONE_TEXT = "无"


MODULE_STATUS_TEXT = {
    ModuleStatus.BOOTSTRAPPED: "可用",
    ModuleStatus.NEXT: "持续完善",
    ModuleStatus.PLANNED: "即将提供",
}

CONNECTION_STATE_TEXT = {
    ConnectionState.DISCONNECTED: "未连接",
    ConnectionState.CONNECTING: "连接中",
    ConnectionState.CONNECTED: "已连接",
    ConnectionState.STOPPING: "停止中",
    ConnectionState.ERROR: "异常",
}

TRANSPORT_KIND_TEXT = {
    TransportKind.SERIAL: "串口",
    TransportKind.TCP_CLIENT: "TCP 客户端",
    TransportKind.TCP_SERVER: "TCP 服务端",
    TransportKind.UDP: "UDP",
    TransportKind.MQTT_CLIENT: "MQTT 客户端",
    TransportKind.MQTT_SERVER: "MQTT 服务端",
}

PAYLOAD_VIEW_TEXT = {
    PayloadViewMode.HEX: "十六进制",
    PayloadViewMode.ASCII: "ASCII 文本",
    PayloadViewMode.UTF8: "UTF-8 文本",
}

RAW_INPUT_MODE_TEXT = {
    RawPacketInputMode.HEX: "十六进制",
    RawPacketInputMode.ASCII: "ASCII 文本",
    RawPacketInputMode.UTF8: "UTF-8 文本",
}

LINE_ENDING_TEXT = {
    RawPacketLineEnding.NONE: "无",
    RawPacketLineEnding.CR: "CR",
    RawPacketLineEnding.LF: "LF",
    RawPacketLineEnding.CRLF: "CRLF",
}

LOG_LEVEL_TEXT = {
    LogLevel.DEBUG: "调试",
    LogLevel.INFO: "信息",
    LogLevel.WARNING: "警告",
    LogLevel.ERROR: "错误",
}

REGISTER_DATA_TYPE_TEXT = {
    RegisterDataType.UINT16: "无符号 16 位",
    RegisterDataType.INT16: "有符号 16 位",
    RegisterDataType.UINT32: "无符号 32 位",
    RegisterDataType.INT32: "有符号 32 位",
    RegisterDataType.FLOAT32: "浮点 32 位",
}

REGISTER_BYTE_ORDER_TEXT = {
    RegisterByteOrder.AB: "AB（标准顺序）",
    RegisterByteOrder.BA: "BA（字节交换）",
    RegisterByteOrder.CDAB: "CDAB（字交换）",
    RegisterByteOrder.BADC: "BADC（字节与字都交换）",
}

SCRIPT_LANGUAGE_TEXT = {
    ScriptLanguage.PYTHON: "Python",
}


def module_status_text(status: ModuleStatus) -> str:
    return MODULE_STATUS_TEXT.get(status, status.value)


def connection_state_text(state: ConnectionState) -> str:
    return CONNECTION_STATE_TEXT.get(state, state.value)


def transport_kind_text(kind: TransportKind) -> str:
    return TRANSPORT_KIND_TEXT.get(kind, kind.value)


def payload_view_text(mode: PayloadViewMode) -> str:
    return PAYLOAD_VIEW_TEXT.get(mode, mode.value)


def raw_input_mode_text(mode: RawPacketInputMode) -> str:
    return RAW_INPUT_MODE_TEXT.get(mode, mode.value)


def line_ending_text(line_ending: RawPacketLineEnding) -> str:
    return LINE_ENDING_TEXT.get(line_ending, line_ending.value)


def log_level_text(level: LogLevel) -> str:
    return LOG_LEVEL_TEXT.get(level, level.value)


def register_data_type_text(data_type: RegisterDataType) -> str:
    return REGISTER_DATA_TYPE_TEXT.get(data_type, data_type.value)


def register_byte_order_text(byte_order: RegisterByteOrder) -> str:
    return REGISTER_BYTE_ORDER_TEXT.get(byte_order, byte_order.value)


def script_language_text(language: ScriptLanguage) -> str:
    return SCRIPT_LANGUAGE_TEXT.get(language, language.value)
