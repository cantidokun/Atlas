// Copyright Epic Games, Inc. All Rights Reserved.
//
// Unreal State Extraction Fidelity v1 — dedicated extraction fixture (declarations).
//
// This is TEST FIXTURE content for the extraction gate, not production extraction code.
// It exists to turn the state-space branches of the Revision 3.1 contract into real
// evidence. It creates:
//
//   * a saved, non-partitioned fixture map holding the tagged actor set (permutation,
//     numbered identities, the three parent states, material assignment/resolution
//     combinations, an omitted-inventory primitive, a null-mesh skinned component, an
//     unsupported component family, signed-zero and quaternion-sign transforms, and one
//     entity-tagged ALevelSequenceActor per sequencer validity arm);
//   * saved, non-transient sequence assets: valid, degenerate-range, unset-range and
//     invalid-rate;
//   * an empty saved sublevel used by the scope-change test seam;
//   * per-session runtime probes that cannot be saved by construction: a dynamic
//     streaming level (loaded and visible) and an actor whose mesh asset is generated at
//     runtime with the runtime-regenerated flags.
//
// Legacy fixtures are not touched: the render fixture, the quarantined sequencer
// integration fixture and the harness transport fixtures keep their own content and code.

#pragma once

#include "CoreMinimal.h"

class UWorld;

namespace AtlasExtractionFixture
{
    /** Map/asset names and entity tags the gate depends on. */
    namespace Names
    {
        extern const TCHAR* const FixtureMapPackage;
        extern const TCHAR* const FixtureMapObjectPath;
        extern const TCHAR* const SublevelPackage;
        extern const TCHAR* const ValidSequencePackage;
        extern const TCHAR* const DegenerateSequencePackage;
        extern const TCHAR* const BadRateSequencePackage;

        /** Entity tags: `atlas_entity:` + the id, one per fixture actor. */
        extern const TCHAR* const PermutationA;
        extern const TCHAR* const PermutationB;
        extern const TCHAR* const CaseLower;
        extern const TCHAR* const CaseUpper;
        extern const TCHAR* const CaseVariantBound;
        extern const TCHAR* const NumberedBase;
        extern const TCHAR* const NumberedOne;
        extern const TCHAR* const NumberedLeadingZero;
        extern const TCHAR* const ParentNone;
        extern const TCHAR* const ParentUnbound;
        extern const TCHAR* const ParentBound;
        extern const TCHAR* const MaterialOverrideA;
        extern const TCHAR* const MaterialOverrideB;
        extern const TCHAR* const OmittedPrimitive;
        extern const TCHAR* const NullSkinned;
        extern const TCHAR* const UnsupportedComponent;
        extern const TCHAR* const SignedZero;
        extern const TCHAR* const QuaternionPositive;
        extern const TCHAR* const QuaternionNegative;
        extern const TCHAR* const SequenceValid;
        extern const TCHAR* const SequenceDegenerate;
        extern const TCHAR* const SequenceBadRate;
        extern const TCHAR* const RuntimeMesh;
    }

    /**
     * Create and save the fixture map, the sublevel and the four sequence assets.
     *
     * Idempotent: an existing saved map/asset is left untouched. Called by the fixture
     * ticker on the first session (or by the fixture commandlet), never by production
     * extraction.
     */
    bool EnsureSavedFixtureContent(FString& OutError);

    /**
     * Ensure the per-session runtime probes in `World` (the world under extraction):
     * a loaded, visible dynamic streaming level and the runtime-generated-mesh actor.
     * Idempotent within a session.
     */
    bool EnsureRuntimeProbeActors(UWorld* World, FString& OutError);

    /** True when `World` is the extraction fixture map. */
    bool IsFixtureWorld(const UWorld* World);

    /** Install/remove the provisioning ticker (called from the module's startup/shutdown). */
    void StartRuntimeFixtureTicker();
    void StopRuntimeFixtureTicker();
}
