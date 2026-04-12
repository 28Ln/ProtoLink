from __future__ import annotations

import socketserver
import threading
from contextlib import suppress
import socket
import asyncio
import warnings
import queue
from uuid import uuid4

from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig
import paho.mqtt.client as mqtt


class _EchoHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            payload = self.request.recv(4096)
            if not payload:
                return
            with self.server.received_lock:
                self.server.received_payloads.append(payload)
            self.request.sendall(payload)


class _ThreadingEchoServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _UdpEchoHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        payload, socket_ref = self.request
        with self.server.received_lock:
            self.server.received_payloads.append(payload)
        socket_ref.sendto(payload, self.client_address)


class _ThreadingUdpEchoServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True
    daemon_threads = True


class TcpEchoServer:
    def __init__(self) -> None:
        self._server = _ThreadingEchoServer(("127.0.0.1", 0), _EchoHandler)
        self._server.received_payloads = []
        self._server.received_lock = threading.Lock()
        self._thread = threading.Thread(target=self._server.serve_forever, name="ProtoLinkTcpEchoServer", daemon=True)

    @property
    def host(self) -> str:
        return str(self._server.server_address[0])

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def target(self) -> str:
        return f"{self.host}:{self.port}"

    def start(self) -> "TcpEchoServer":
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)

    def received_payloads(self) -> list[bytes]:
        with self._server.received_lock:
            return list(self._server.received_payloads)

    def __enter__(self) -> "TcpEchoServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class UdpEchoServer:
    def __init__(self) -> None:
        self._server = _ThreadingUdpEchoServer(("127.0.0.1", 0), _UdpEchoHandler)
        self._server.received_payloads = []
        self._server.received_lock = threading.Lock()
        self._thread = threading.Thread(target=self._server.serve_forever, name="ProtoLinkUdpEchoServer", daemon=True)

    @property
    def host(self) -> str:
        return str(self._server.server_address[0])

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def target(self) -> str:
        return f"{self.host}:{self.port}"

    def start(self) -> "UdpEchoServer":
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)

    def received_payloads(self) -> list[bytes]:
        with self._server.received_lock:
            return list(self._server.received_payloads)

    def __enter__(self) -> "UdpEchoServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class MqttTestBroker:
    def __init__(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self._port = int(sock.getsockname()[1])
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ProtoLinkMqttBroker", daemon=True)
        self._broker: Broker | None = None

    @property
    def host(self) -> str:
        return "127.0.0.1"

    @property
    def port(self) -> int:
        return self._port

    @property
    def target(self) -> str:
        return f"{self.host}:{self.port}"

    def start(self) -> "MqttTestBroker":
        self._thread.start()
        self._ready.wait(timeout=5.0)
        return self

    def _run(self) -> None:
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        asyncio.set_event_loop(self._loop)
        config = BrokerConfig.from_dict({"listeners": {"default": {"bind": self.target}}})
        self._broker = Broker(config, loop=self._loop)
        self._loop.run_until_complete(self._broker.start())
        self._ready.set()
        self._loop.run_forever()
        self._loop.run_until_complete(self._broker.shutdown())
        self._loop.close()

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)

    def __enter__(self) -> "MqttTestBroker":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class MqttExternalClient:
    def __init__(self, host: str, port: int, *, client_id: str = "protolink-test-client") -> None:
        self._messages: "queue.Queue[tuple[str, bytes]]" = queue.Queue()
        self._connected = threading.Event()
        self._subscribed = threading.Event()
        unique_client_id = f"{client_id}-{uuid4().hex[:8]}"
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=unique_client_id,
            protocol=mqtt.MQTTv311,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe
        self._client.connect(host, port, 60)
        self._client.loop_start()
        self._connected.wait(timeout=5.0)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._connected.set()

    def _on_message(self, client, userdata, msg) -> None:
        self._messages.put((msg.topic, bytes(msg.payload)))

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None) -> None:
        self._subscribed.set()

    def subscribe(self, topic: str) -> None:
        self._subscribed.clear()
        self._client.subscribe(topic)
        self._subscribed.wait(timeout=5.0)

    def publish(self, topic: str, payload: bytes) -> None:
        info = self._client.publish(topic, payload=payload, qos=0)
        info.wait_for_publish()

    def recv(self, timeout: float = 2.0) -> tuple[str, bytes]:
        return self._messages.get(timeout=timeout)

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def __enter__(self) -> "MqttExternalClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class TcpSocketClient:
    def __init__(self, host: str, port: int, *, timeout: float = 2.0) -> None:
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.settimeout(timeout)

    def send(self, payload: bytes) -> None:
        self._socket.sendall(payload)

    def recv(self, size: int = 4096) -> bytes:
        return self._socket.recv(size)

    def close(self) -> None:
        with suppress(Exception):
            self._socket.shutdown(socket.SHUT_RDWR)
        self._socket.close()

    def __enter__(self) -> "TcpSocketClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
