#pragma once

#include "CoreMinimal.h"
#include "AtlasLiveIngressQueue.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include <atomic>

/**
 * Connection lifecycle states for Atlas Live TCP Receiver.
 */
enum class EAtlasLiveConnectionState : uint8
{
    Disconnected = 0,
    Listening,
    Connecting,
    Connected,
    Disconnecting
};

/**
 * Telemetry counters specific to the TCP transport layer.
 */
struct FAtlasLiveTcpTelemetry
{
    EAtlasLiveConnectionState ConnectionState = EAtlasLiveConnectionState::Disconnected;
    uint32 BoundPort = 0;
    int64 TotalBytesReceived = 0;
    int64 TotalFramesReceived = 0;
    int64 TotalFramesRejected = 0;
    int64 TotalMalformedFrames = 0;
    int64 TotalOversizedFrames = 0;
    int64 TotalBadVersionFrames = 0;
    int64 TotalDigestFailures = 0;
    int64 TotalDisconnects = 0;
    int64 TotalReconnects = 0;
    double LastFrameDecodeDurationMs = 0.0;
};

/**
 * Asynchronous, non-blocking TCP socket listener thread for Atlas Live.
 * 
 * Binds strictly to 127.0.0.1.
 * Frame Protocol:
 * [uint32 BigEndian payload_len] [uint8 protocol_version] [canonical envelope payload bytes]
 *
 * Runs completely OFF the GameThread.
 * Deserializes JSON ProductionIntentEnvelope, checks SHA-256 digest, and enqueues into FAtlasLiveIngressQueue.
 * Never waits for GameThread.
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveTcpListener : public FRunnable
{
public:
    static constexpr uint8 CurrentProtocolVersion = 1;
    static constexpr uint32 MaxAllowedPayloadLength = 65536; // 64 KB hard ceiling
    static constexpr uint32 HeaderLength = 5; // 4 bytes length + 1 byte version

    FAtlasLiveTcpListener(
        TSharedPtr<FAtlasLiveIngressQueue> InQueue,
        int32 InListenPort = 0, // 0 = dynamic OS assigned port
        const FString& InBindAddress = TEXT("127.0.0.1"));

    virtual ~FAtlasLiveTcpListener();

    // Non-copyable
    FAtlasLiveTcpListener(const FAtlasLiveTcpListener&) = delete;
    FAtlasLiveTcpListener& operator=(const FAtlasLiveTcpListener&) = delete;

    /** Start listener thread */
    bool Start();

    /** Stop listener and close all sockets cleanly */
    void StopListener();

    // FRunnable interface
    virtual bool Init() override;
    virtual uint32 Run() override;
    virtual void Stop() override;
    virtual void Exit() override;

    /** Port actually bound to (useful when InListenPort == 0) */
    int32 GetBoundPort() const { return BoundPort; }

    /** Telemetry snapshot */
    FAtlasLiveTcpTelemetry GetTelemetry() const;

    /** Current connection lifecycle state */
    EAtlasLiveConnectionState GetConnectionState() const { return ConnectionState.load(std::memory_order_relaxed); }

    /** Static helper to parse and validate a single raw frame payload */
    static bool ParseAndValidateEnvelope(
        const uint8* PayloadBytes,
        int32 PayloadLength,
        FAtlasLiveProductionIntent& OutIntent,
        FString& OutError);

private:
    void CleanUpSockets();
    void ProcessClientStream(FSocket* ClientSocket);
    bool ReadExact(FSocket* Socket, uint8* OutBuffer, int32 BytesToRead, const FTimespan& Timeout);

    TSharedPtr<FAtlasLiveIngressQueue> IngressQueue;
    int32 DesiredPort;
    FString BindAddressStr;
    std::atomic<int32> BoundPort;

    FRunnableThread* Thread;
    FThreadSafeBool bStopRequested;

    FSocket* ListenSocket;
    FSocket* ActiveClientSocket;

    std::atomic<EAtlasLiveConnectionState> ConnectionState;
    std::atomic<int64> TotalBytesReceivedCount;
    std::atomic<int64> TotalFramesReceivedCount;
    std::atomic<int64> TotalFramesRejectedCount;
    std::atomic<int64> TotalMalformedFramesCount;
    std::atomic<int64> TotalOversizedFramesCount;
    std::atomic<int64> TotalBadVersionFramesCount;
    std::atomic<int64> TotalDigestFailuresCount;
    std::atomic<int64> TotalDisconnectsCount;
    std::atomic<int64> TotalReconnectsCount;
    std::atomic<double> LastFrameDecodeDurationMs;

    int32 CurrentSessionCounter;
};
