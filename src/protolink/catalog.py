from __future__ import annotations

from protolink.core.models import FeatureModule, ModuleStatus


def build_module_catalog() -> list[FeatureModule]:
    return [
        FeatureModule(
            name="Dashboard",
            area="Foundation",
            milestone="M0",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Project shell, workspace status, and module navigation baseline.",
            acceptance=(
                "Application starts successfully.",
                "Workspace is initialized automatically.",
                "Navigation is stable and consistent.",
            ),
        ),
        FeatureModule(
            name="Serial Studio",
            area="Transport",
            milestone="M1",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Unified serial connection lifecycle, send/receive console, and raw-byte capture.",
            acceptance=(
                "Serial ports can be enumerated and opened.",
                "Send/receive logs retain raw bytes.",
                "Connection errors are surfaced without freezing the UI.",
            ),
        ),
        FeatureModule(
            name="Modbus RTU Lab",
            area="Protocol",
            milestone="M2",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Dedicated Modbus RTU workflow entry with request composition, serial dispatch, register-monitor integration, and packet-inspector decode linkage.",
            acceptance=(
                "RTU frame composer and parser agree on raw bytes.",
                "Requests can be dispatched through an active RTU-capable transport.",
                "Register monitoring and packet-inspector decode stay on the same workflow path.",
            ),
        ),
        FeatureModule(
            name="Modbus TCP Lab",
            area="Protocol",
            milestone="M2",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Dedicated Modbus TCP workflow entry with request composition, TCP client dispatch, register-monitor integration, and packet-inspector decode linkage.",
            acceptance=(
                "TCP request composition and parser output agree on the same payload bytes.",
                "Requests can be dispatched through an active TCP client.",
                "Register monitoring and packet-inspector decode stay on the same workflow path.",
            ),
        ),
        FeatureModule(
            name="MQTT Client",
            area="Transport",
            milestone="M1",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Broker connection with baseline subscribe/publish workflow and shared packet inspection.",
            acceptance=(
                "Client can connect, subscribe, and publish.",
                "Payload format conversions are explicit and repeatable.",
            ),
        ),
        FeatureModule(
            name="MQTT Server",
            area="Transport",
            milestone="M1",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Local broker mode with baseline start/stop, broker publish, and shared packet inspection.",
            acceptance=(
                "Server can start and stop cleanly.",
                "Auth and message logging are independently configurable.",
            ),
        ),
        FeatureModule(
            name="TCP Client",
            area="Transport",
            milestone="M1",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Raw socket client with baseline session service, send controls, and shared packet inspection.",
            acceptance=(
                "Client lifecycle is consistent with other transports.",
                "Received payloads can be inspected and exported.",
            ),
        ),
        FeatureModule(
            name="TCP Server",
            area="Transport",
            milestone="M1",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Local server mode with baseline listener lifecycle, client counting, broadcast send controls, and shared packet inspection.",
            acceptance=(
                "Server accepts multiple sessions safely.",
                "Per-session visibility and broadcast behavior are explicit.",
            ),
        ),
        FeatureModule(
            name="UDP Lab",
            area="Transport",
            milestone="M1",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Connectionless messaging with baseline bind/send workflow, remote target controls, and shared packet inspection.",
            acceptance=(
                "Bind and send behavior are separately controllable.",
                "Inbound and outbound payloads are retained in logs.",
            ),
        ),
        FeatureModule(
            name="Packet Inspector",
            area="Shared",
            milestone="M2",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Shared packet inspection shell with raw payload views, bytes-first composer, and event-bus-backed log ingestion.",
            acceptance=(
                "Every transport can publish to the same packet inspector model.",
                "Raw bytes remain available after decode failures.",
                "Raw packet drafts can be composed and previewed with bytes-first visibility.",
                "Selected payload rows can render baseline Modbus RTU/TCP decode with protocol validation.",
                "Replay plans can be loaded and dispatched to active transport sessions from the inspector dock.",
                "Visible inspector rows can be exported into replay plan files for iterative playback.",
            ),
        ),
        FeatureModule(
            name="Register Monitor",
            area="Shared",
            milestone="M2",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Reusable monitoring surface for register-based protocols and device templates, with baseline point models and decode panel now in place.",
            acceptance=(
                "Register metadata can be imported and exported.",
                "Byte order and scaling rules are explicit.",
            ),
        ),
        FeatureModule(
            name="Automation Rules",
            area="Automation",
            milestone="M3",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Rule-based match, transform, and respond pipeline across transports, with baseline runtime wiring, runtime safety controls, and a minimal management panel in place.",
            acceptance=(
                "Rules can be started and stopped safely.",
                "Rule matches are visible and auditable.",
                "Automation runtime stop/disable boundaries stay explicit before wider owner-surface expansion.",
            ),
        ),
        FeatureModule(
            name="Script Console",
            area="Automation",
            milestone="M3",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Workspace-owned script execution surface on top of the bounded script host, with output/error visibility and saved script evidence.",
            acceptance=(
                "Scripts run in a controlled host.",
                "Logs and failures are attached to the same workspace.",
            ),
        ),
        FeatureModule(
            name="Data Tools",
            area="Shared",
            milestone="M2",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Deterministic encoding, checksum, format conversion, and JSON helper tools exposed through an owner surface independent from transport state.",
            acceptance=(
                "Tools can be opened independently from transport state.",
                "Conversions are deterministic and test-covered.",
            ),
        ),
        FeatureModule(
            name="Network Tools",
            area="Ops",
            milestone="M4",
            status=ModuleStatus.BOOTSTRAPPED,
            summary="Windows-oriented read-only-first local network diagnostics with explicit non-write boundaries and connectivity checks.",
            acceptance=(
                "Privileged operations are clearly separated.",
                "Every change path includes confirmation and rollback guidance.",
            ),
        ),
    ]
