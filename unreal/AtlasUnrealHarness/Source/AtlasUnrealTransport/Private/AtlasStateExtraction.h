// Copyright Epic Games, Inc. All Rights Reserved.
//
// Unreal State Extraction Fidelity v1 — read-only extraction core (declarations).
//
// Contract: docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md, Revision 3.3
// (design branch feat/unreal-state-extraction-fidelity-v1-design, PR #106).
//
// Architectural placement (design §10.2 items 1-2):
//   * this header and AtlasStateExtraction.cpp form their own translation unit;
//   * the extractor is NOT a member of FAtlasTransportServer, receives no pointer or
//     reference to it, and never calls back into it;
//   * the server's dispatcher holds the single one-way seam that calls in here and
//     receives either a value tree or one code from the closed error vocabulary.
//
// Authority (design §2, §3.1): the extractor is a pure read. It selects the world itself
// from GEditor->GetEditorWorldContext().World() — never through the existing, order
// dependent helpers — because world selection is part of the contract (§3.1.1).

#pragma once

#include "CoreMinimal.h"

class FJsonObject;

namespace AtlasStateExtraction
{
    /** The closed producer error vocabulary of design §8.1. */
    namespace ErrorCodes
    {
        extern const TCHAR* const RequestInvalid;
        extern const TCHAR* const WorldUnavailable;
        extern const TCHAR* const WorldNotEditor;
        extern const TCHAR* const WorldPartitionUnsupported;
        extern const TCHAR* const LevelScopeIncomplete;
        extern const TCHAR* const LevelScopeInvalid;
        extern const TCHAR* const ScopeChanged;
        extern const TCHAR* const EntityNotFound;
        extern const TCHAR* const EntityAmbiguous;
        extern const TCHAR* const EntityTagConflict;
        extern const TCHAR* const UnsupportedComponentType;
        extern const TCHAR* const EngineIdentityUnavailable;
        extern const TCHAR* const ParentTagConflict;
        extern const TCHAR* const NonFinite;
        extern const TCHAR* const MeshCompiling;
        extern const TCHAR* const MeshAssetUnstable;
        extern const TCHAR* const MaterialUnresolved;
        extern const TCHAR* const UnsupportedMaterialSource;
        extern const TCHAR* const SequenceActorType;
        extern const TCHAR* const SequenceAssetUnresolved;
        extern const TCHAR* const UnsupportedSequenceSource;
        extern const TCHAR* const SequenceRangeOpen;
        extern const TCHAR* const SequenceRangeInvalid;
        extern const TCHAR* const SequenceRateInvalid;
        extern const TCHAR* const PayloadTooLarge;
    }

    /**
     * Build an `actor_state` value tree for the requested canonical entity IDs.
     *
     * @param EntityIds      the request's entity IDs (request spelling; canonicalised here)
     * @param OutValueTree   the value tree under `unreal_state_extraction`, on success
     * @param OutError       human-readable failure detail
     * @param OutErrorCode   exactly one code from the closed vocabulary, on failure
     * @return true only when a complete value tree was produced; a failed extraction
     *         returns no tree and no partial payload (design §8.2)
     */
    bool ExtractActorState(
        const TArray<FString>& EntityIds,
        TSharedPtr<FJsonObject>& OutValueTree,
        FString& OutError,
        FString& OutErrorCode);

    /** Build a `sequencer_state` value tree for exactly one canonical entity ID. */
    bool ExtractSequencerState(
        const TArray<FString>& EntityIds,
        TSharedPtr<FJsonObject>& OutValueTree,
        FString& OutError,
        FString& OutErrorCode);

    /**
     * Test-only scope-revalidation probe.
     *
     * The contract requires the extraction to fail closed when the world's level scope
     * changes between the snapshot and the post-scan re-query (§3.2.1.4b). No production
     * read can induce that transition, and the design forbids the extractor from causing
     * it, so the extractor exposes a single, null-by-default callback that runs *between*
     * the snapshot and the re-query.
     *
     * Properties that keep this production-safe:
     *   * the default is null, and nothing in the transport or the dispatcher ever sets it;
     *   * the callback is invoked synchronously on the game thread — no waits, no task
     *     hops, no polling — so the extractor's execution guarantees are unchanged;
     *   * the extractor itself performs no mutation; whatever the callback does is the
     *     test's business and is attributed to the test;
     *   * only the extraction gate's own automation test uses it.
     */
    using FScopeProbe = TFunction<void()>;
    void SetScopeRevalidationProbe(FScopeProbe InProbe);
    void ClearScopeRevalidationProbe();

    /**
     * §9 item 3 capacity measurement: the UTF-8 byte count of a value tree serialized under
     * the same writer policy the transport uses (`TJsonWriterFactory<>` + `FJsonSerializer`),
     * which is exactly the encoding `WriteResponse` puts on the wire. Returns -1 when the
     * tree is invalid or cannot be serialized; callers must treat that as a failure.
     *
     * Exposed so the extraction gate can prove boundary behaviour on a deliberately
     * constructed payload instead of inspecting the limit constant.
     */
    int32 MeasureValueTreeBytes(const TSharedPtr<FJsonObject>& ValueTree);

    /**
     * §9 item 3 early necessary condition: refuse with `ERR_EXTRACTION_PAYLOAD_TOO_LARGE`
     * when the value tree *alone* is at or above the transport bound, because the response
     * (tree + envelope) then cannot fit. No envelope allowance is assumed. The decisive
     * check measures the serialized response where the response is produced, so a payload
     * that survives this check and does not fit still fails closed before crossing the wire.
     */
    bool CheckPayloadBound(
        const TSharedPtr<FJsonObject>& ValueTree,
        FString& OutError,
        FString& OutErrorCode);
}
