"""Real localhost TCP client transport channel for Atlas Live.

Implements LiveTransportChannel delivering ProductionIntents across a persistent TCP
connection to Unreal Engine's FAtlasLiveTcpListener.

Frame Protocol (v1):
[4 bytes uint32 big-endian payload_length]
[1 byte  uint8  protocol_version (1)]
[canonical ProductionIntentEnvelope JSON bytes]
"""

from dataclasses import dataclass
from enum import Enum
import json
import socket
import struct
import time
from typing import List, Optional, Sequence

from live.production_intent import ProductionIntent, ProductionIntentEnvelope
from live.transport import DeliveryReceipt, DeliveryStatus, LiveTransportChannel


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


class TcpTransportChannel:
    """Production localhost TCP transport channel for Atlas Live.

    Attributes:
        host: Target IP (strictly 127.0.0.1 for local isolation).
        port: Unreal Live TCP listen port.
        protocol_version: Wire protocol version byte (1).
        max_payload_length: Hard ceiling for frame size (default 65536 bytes).
    """

    PROTOCOL_VERSION = 1
    MAX_PAYLOAD_LENGTH = 65536
    HEADER_SIZE = 5

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7777,
        max_buffer_size: int = 128,
        timeout_s: float = 1.0,
    ) -> None:
        self.host = host
        self.port = port
        self.max_buffer_size = max_buffer_size
        self.timeout_s = timeout_s

        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._sock: Optional[socket.socket] = None
        self._next_sequence: int = 1
        self._receipts: List[DeliveryReceipt] = []

        # Outgoing telemetry
        self.total_bytes_sent: int = 0
        self.total_frames_sent: int = 0
        self.total_send_errors: int = 0

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED and self._sock is not None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def receipts(self) -> Sequence[DeliveryReceipt]:
        return tuple(self._receipts)

    def connect(self) -> bool:
        """Establish persistent TCP connection with TCP_NODELAY."""
        if self.is_connected:
            return True

        self._state = ConnectionState.CONNECTING
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(self.timeout_s)
            sock.connect((self.host, self.port))
            self._sock = sock
            self._state = ConnectionState.CONNECTED
            return True
        except (socket.error, OSError) as e:
            self._state = ConnectionState.DISCONNECTED
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            return False

    def disconnect(self) -> None:
        """Cleanly close connection."""
        self._state = ConnectionState.DISCONNECTING
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._state = ConnectionState.DISCONNECTED

    @classmethod
    def encode_frame(
        cls,
        sequence_number: int,
        intent: ProductionIntent,
        sent_at_ns: int,
        protocol_version: int = PROTOCOL_VERSION,
    ) -> bytes:
        """Format an intent into exact wire framing: [uint32 len][uint8 ver][JSON envelope]."""
        envelope = ProductionIntentEnvelope.create(
            sequence_number=sequence_number,
            intent=intent,
            sent_at_ns=sent_at_ns,
        )

        envelope_dict = {
            "sequence_number": envelope.sequence_number,
            "sent_at_ns": envelope.sent_at_ns,
            "digest": envelope.digest,
            "intent": intent.to_dict(),
        }

        payload_bytes = json.dumps(envelope_dict, separators=(",", ":")).encode("utf-8")
        if len(payload_bytes) > cls.MAX_PAYLOAD_LENGTH:
            raise ValueError(
                f"Payload size {len(payload_bytes)} exceeds maximum {cls.MAX_PAYLOAD_LENGTH}"
            )

        header = struct.pack("!IB", len(payload_bytes), protocol_version)
        return header + payload_bytes

    def send(self, intent: ProductionIntent) -> DeliveryReceipt:
        """Send an intent across the TCP transport boundary."""
        now_ns = time.perf_counter_ns()
        seq = self._next_sequence
        self._next_sequence += 1

        if not self.is_connected:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_DISCONNECTED,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest="",
                error_message="TCP transport channel is not connected",
            )
            self._receipts.append(receipt)
            return receipt

        try:
            frame_bytes = self.encode_frame(
                sequence_number=seq,
                intent=intent,
                sent_at_ns=now_ns,
                protocol_version=self.PROTOCOL_VERSION,
            )

            # Sendall across socket
            assert self._sock is not None
            self._sock.sendall(frame_bytes)

            delivered_ns = time.perf_counter_ns()
            self.total_bytes_sent += len(frame_bytes)
            self.total_frames_sent += 1

            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.DELIVERED,
                sent_at_ns=now_ns,
                delivered_at_ns=delivered_ns,
                digest="",
            )
            self._receipts.append(receipt)
            return receipt

        except (socket.timeout, TimeoutError) as e:
            self.total_send_errors += 1
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_TIMEOUT,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest="",
                error_message=f"TCP send timeout: {str(e)}",
            )
            self._receipts.append(receipt)
            return receipt

        except (socket.error, OSError) as e:
            self.total_send_errors += 1
            self.disconnect()
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_DISCONNECTED,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest="",
                error_message=f"TCP send error, disconnected: {str(e)}",
            )
            self._receipts.append(receipt)
            return receipt
