# Atlas Live — TCP Streaming Wire Protocol (v1)

## 1. Specification Overview

The Atlas Live TCP Streaming Transport provides high-frequency, low-latency delivery of validated `ProductionIntent` envelopes from Python Atlas Live to Unreal Engine.

- **Transport**: TCP
- **Binding**: `127.0.0.1` (localhost only)
- **Socket Options**: `TCP_NODELAY = 1` (Nagle disabled on both client and server)
- **Connection Model**: Persistent stream connection, non-blocking asynchronous reception.
- **Port**: Default `7778` (configurable / fallback to OS dynamic port).

---

## 2. Binary Frame Framing

Every frame transmitted over the TCP stream has the following structure:

```text
+-----------------------+--------------------+----------------------------------------+
| payload_length        | protocol_version   | canonical envelope payload bytes       |
| uint32 (4 bytes, BE)  | uint8 (1 byte)     | JSON UTF-8 string (length bytes)       |
+-----------------------+--------------------+----------------------------------------+
```

### Fields

1. **`payload_length`** (`uint32`, 4 bytes, Big-Endian):
   - Strict length in bytes of the following envelope payload.
   - Enforces $1 \le \text{payload\_length} \le 65536$ (64 KB ceiling).
   - Any frame with `payload_length == 0` or `payload_length > 65536` triggers immediate disconnection and malformed rejection telemetry.

2. **`protocol_version`** (`uint8`, 1 byte):
   - Current version: `1` (`0x01`).
   - Receivers reject any frame where `protocol_version != 1` and disconnect to prevent protocol desynchronization.

3. **`canonical envelope payload bytes`** (UTF-8 JSON string):
   - Canonical `ProductionIntentEnvelope` representation:
     ```json
     {
       "sequence_number": 1,
       "sent_at_ns": 1000000,
       "digest": "sha256_hex_digest",
       "intent": {
         "intent_id": "intent-0001",
         "treatment": "impact_accent",
         "source_event_id": "evt-0001",
         "target_entity_ids": ["player-09"],
         "intensity": 0.85,
         "duration_ms": 200,
         "timestamp_ns": 1000000,
         "origin": {"x": 10.0, "y": 0.0, "z": 0.1},
         "direction": {"x": 1.0, "y": 0.0, "z": 0.0},
         "parameters": {"preset": "strike_flash_v1"}
       }
     }
     ```

---

## 3. Envelope Integrity & SHA-256 Digest

To guarantee content integrity and prevent corruption across process boundaries:

$$\text{digest} = \text{SHA256}\left(\text{UTF8}(\texttt{f"\{sequence\_number\}:\{sent\_at\_ns\}:"\}) + \text{UTF8}(\text{IntentJSON})\right)$$

- On the Unreal receiver thread, the payload is parsed, the canonical header and intent JSON bytes are extracted, and SHA-256 is computed using Windows `BCrypt` (`BCRYPT_SHA256_ALGORITHM`).
- If `digest != computed_digest`, the message is rejected with `TotalDigestFailures` incremented and never reaches the ingress queue or GameThread.

---

## 4. Connection Lifecycle & State Transitions

```text
[DISCONNECTED]
      │
      ▼ (socket.connect)
[CONNECTING]
      │
      ▼ (handshake / accept)
[CONNECTED] ◄─── (streaming frames)
      │
      ▼ (EOF / error / protocol violation)
[DISCONNECTING]
      │
      ▼
[DISCONNECTED] ──► (reconnect resets session domain) ──► [CONNECTING]
```

### Delivery Semantics Clarification
- In Python, `DeliveryStatus.DELIVERED` indicates that the local socket send operation completed successfully (`sendall` finished).
- It does **NOT** indicate that Unreal Engine received, enqueued, processed, or dispatched the visual effect on the GameThread.
- Bidirectional backpressure and delivery ACK protocols remain deliberately deferred for future milestones.

### Failure & Reconnection Semantics
- **Reconnection**: Handled cleanly without restarting Unreal. A new client connection creates a new `SessionId` (e.g. `tcp-session-2`), resetting sequence number tracking so the client can resume starting at `sequence_number = 1`.
- **Partial Reads**: The receiver uses `ReadExact` to assemble full frames regardless of TCP segment fragmentation or concatenation (multiple frames per `recv`).
- **GameThread Isolation**: TCP receiver thread never waits for GameThread execution. Enqueues into `FAtlasLiveIngressQueue` are $O(1)$ and thread-safe.
- **Offline RPC Isolation**: The offline Named Pipe RPC server (`FAtlasTransportServer`) remains completely untouched and independent.

---

## 5. Clock Domains & Latency Telemetry

Monotonic clocks between Python (`time.perf_counter_ns()`) and Unreal (`FPlatformTime::Cycles64()`) are distinct and never directly subtracted.

### Telemetry Segments:
1. **Python Host Domain**:
   - $\Delta t_{\text{creation}} \to \Delta t_{\text{serialize}} \to \Delta t_{\text{send\_start}} \to \Delta t_{\text{send\_finish}}$
2. **Unreal In-Process Domain**:
   - $T_{\text{recv}}$: Receiver socket read completion (`ReceiverCycles`).
   - $T_{\text{decode}}$: Envelope parse and SHA-256 validation complete (`ValidatedCycles`).
   - $T_{\text{enqueue}}$: Insertion into `FAtlasLiveIngressQueue` (`EnqueuedCycles`).
   - $T_{\text{dequeue}}$: GameThread pump pop (`DequeuedCycles`).
   - $T_{\text{dispatch}}$: Visual effect / dispatcher execution (`DispatchedCycles`).
3. **Queue Wait Latency**:
   $$\Delta t_{\text{queue}} = \text{CyclesToMs}(T_{\text{dequeue}} - T_{\text{enqueue}})$$
4. **Dispatch Execution Latency**:
   $$\Delta t_{\text{dispatch}} = \text{CyclesToMs}(T_{\text{dispatch\_end}} - T_{\text{dispatch\_start}})$$
