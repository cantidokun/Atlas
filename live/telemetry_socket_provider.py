"""Live UDP tracking telemetry ingress adapter for Atlas Live.

Provides non-blocking, bounded UDP datagram ingestion for tracking telemetry:
- Datagram framing: one UTF-8 encoded JSON object per UDP datagram.
- Bounded internal queue with drop-oldest policy under backpressure.
- Non-blocking poll interface: poll_raw_frame() returns Optional[RawPerceptionFrame].
- Strict upstream separation: ZERO WorldState, identity, event, or Unreal logic.
- Preserves provider/session/track provenance and timestamp-domain metadata.
- Exposes typed telemetry for packets received, dropped, and rejected.
"""

from dataclasses import dataclass
import json
import queue
import socket
import threading
from typing import Dict, Mapping, Optional, Tuple

from live.perception_adapter import RawPerceptionFrame
from live.telemetry_provider import TelemetryStreamProvider


@dataclass(frozen=True)
class SocketIngressTelemetry:
    """Telemetry counters for live UDP tracking ingestion."""

    packets_received: int = 0
    packets_accepted: int = 0
    packets_dropped_overflow: int = 0
    packets_rejected_malformed: int = 0
    packets_rejected_oversized: int = 0
    bytes_received: int = 0


# Conservative unfragmented UDP datagram payload limit.
# Standard Ethernet MTU is 1500 bytes; IPv4 header is 20-60 bytes, UDP header is 8 bytes.
# Max unfragmented payload size over standard Ethernet: 1500 - 20 - 8 = 1472 bytes.
DEFAULT_MAX_DATAGRAM_BYTES: int = 1472


class LiveTelemetryUdpReceiver:
    """Non-blocking UDP receiver for tracking telemetry datagrams.

    Binds a local UDP port, reads datagrams in a background daemon thread,
    validates JSON structure into RawPerceptionFrame via TelemetryStreamProvider,
    and enqueues frames into a bounded queue with drop-oldest overflow behavior.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,  # 0 binds an ephemeral OS-assigned port
        max_queue_size: int = 128,
        max_datagram_bytes: int = DEFAULT_MAX_DATAGRAM_BYTES,
        provider: Optional[TelemetryStreamProvider] = None,
    ) -> None:
        self.host = host
        self.requested_port = port
        self.max_queue_size = max_queue_size
        self.max_datagram_bytes = max_datagram_bytes
        self.provider = provider or TelemetryStreamProvider()

        self._socket: Optional[socket.socket] = None
        self._bound_port: int = 0
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._queue: queue.Queue[RawPerceptionFrame] = queue.Queue(maxsize=max_queue_size)

        # Telemetry counters
        self._packets_received = 0
        self._packets_accepted = 0
        self._packets_dropped_overflow = 0
        self._packets_rejected_malformed = 0
        self._packets_rejected_oversized = 0
        self._bytes_received = 0
        self._lock = threading.Lock()

    @property
    def bound_port(self) -> int:
        return self._bound_port

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def telemetry(self) -> SocketIngressTelemetry:
        with self._lock:
            return SocketIngressTelemetry(
                packets_received=self._packets_received,
                packets_accepted=self._packets_accepted,
                packets_dropped_overflow=self._packets_dropped_overflow,
                packets_rejected_malformed=self._packets_rejected_malformed,
                packets_rejected_oversized=self._packets_rejected_oversized,
                bytes_received=self._bytes_received,
            )

    def start(self) -> bool:
        """Start UDP listener on background thread."""
        if self._is_running:
            return True

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(0.2)  # 200ms recv timeout for graceful thread termination
            self._socket.bind((self.host, self.requested_port))
            self._bound_port = self._socket.getsockname()[1]
        except Exception:
            if self._socket:
                self._socket.close()
                self._socket = None
            return False

        self._is_running = True
        self._thread = threading.Thread(target=self._run_receiver, daemon=True, name="AtlasLiveUdpTelemetryReceiver")
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop background receiver and close socket."""
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def poll_raw_frame(self) -> Optional[RawPerceptionFrame]:
        """Non-blocking poll for next valid frame.

        Returns None immediately if queue is empty.
        """
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def _run_receiver(self) -> None:
        # Buffer slightly larger than max_datagram_bytes to detect oversized datagrams
        recv_buf_size = max(self.max_datagram_bytes + 2048, 65535)
        while self._is_running and self._socket:
            try:
                data, _ = self._socket.recvfrom(recv_buf_size)
            except socket.timeout:
                continue
            except Exception:
                if not self._is_running:
                    break
                continue

            with self._lock:
                self._packets_received += 1
                self._bytes_received += len(data)

            # Check conservative MTU / datagram size limit
            if len(data) > self.max_datagram_bytes:
                with self._lock:
                    self._packets_rejected_oversized += 1
                continue

            # Decode UTF-8 string
            try:
                text = data.decode("utf-8").strip()
            except UnicodeDecodeError:
                with self._lock:
                    self._packets_rejected_malformed += 1
                continue

            if not text:
                with self._lock:
                    self._packets_rejected_malformed += 1
                continue

            # Parse via TelemetryStreamProvider
            try:
                raw_frame = self.provider.parse_telemetry_line(text)
            except Exception:
                raw_frame = None

            if raw_frame is None:
                with self._lock:
                    self._packets_rejected_malformed += 1
                continue

            # Enqueue with drop-oldest overflow policy
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    with self._lock:
                        self._packets_dropped_overflow += 1
                except queue.Empty:
                    pass

            try:
                self._queue.put_nowait(raw_frame)
                with self._lock:
                    self._packets_accepted += 1
            except queue.Full:
                with self._lock:
                    self._packets_dropped_overflow += 1
