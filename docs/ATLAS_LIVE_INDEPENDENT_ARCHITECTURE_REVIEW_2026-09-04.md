# Atlas Live — Independent Senior Architecture Review

**Reviewer stance:** Independent, adversarial. Passing tests, a clean Unreal build, and a working vertical
slice are treated as evidence that the *demonstrated path* works, not as evidence that the *architecture*
is correct for where Atlas Live is going. This review reads the actual implementation
(`live/*.py`, `AtlasUnrealTransport`, wire docs) and challenges it against the ten target capabilities:
real perception, multi-sensor fusion, prediction, tactical/cinematic intelligence, and incremental
Python → C++ replacement.

Scope reviewed: `live/perception_adapter.py`, `live/observation.py`, `live/world_state.py`,
`live/event_engine.py`, `live/production_intent.py`, `live/transport.py`, `live/tcp_transport.py`,
`live/runtime_coordinator.py`, `live/simulated_provider.py`, `live/unreal_consumer.py`,
`AtlasLiveIngressQueue.{h,cpp}`, `AtlasLiveGameThreadPump.cpp`, `AtlasLiveEffectRegistry.{h,cpp}`,
`AtlasLiveTcpListener.cpp`, `AtlasLiveImpactAccentHandler.cpp`, `AtlasLiveImpactFrameHandler.cpp`,
`AtlasLiveSpeedTrailHandler.h`, `AtlasLiveIngressQueueTest.cpp`, `AtlasLiveEffectDispatchTest.cpp`,
plus `docs/ATLAS_LIVE_ARCHITECTURE_SNAPSHOT.md`, `ATLAS_LIVE_TEMPORAL_INGESTION_BOUNDARY.md`,
`ATLAS_LIVE_TCP_WIRE_PROTOCOL.md`, `ATLAS_LIVE_ARCHITECTURE_DIRECTION.md`, `ATLAS_LIVE_REPOSITORY_AUDIT_2026-09-04.md`,
and `planning/live_world_state.py` (a second, unrelated "LiveWorldState" that predates this one — see finding 0).

---

## 0. CRITICAL — Two unrelated "LiveWorldState" implementations coexist

**Subsystem:** World-state model / naming.

**Issue:** `planning/live_world_state.py` defines `LiveWorldStateSnapshot`, `LiveEntityState`,
`LiveWorldStateEnvelope`, `validate_live_world_state` — a pure identity/sequence validator with no
kinematics, no derived velocity, no reconciliation loop. `live/world_state.py` defines a *different*
`LiveWorldState` / `LiveWorldEntity` / `LiveWorldStateReconciler` that is the one actually wired into the
vertical slice (`runtime_coordinator.py`). Both are exercised by tests (`tests/test_live_world_state.py`
imports from `planning.live_world_state`; `tests/test_live_vertical_slice.py` imports from
`live.world_state`). Nothing marks either as deprecated. A future contributor (or an LLM agent) searching
for "the world state" has a 50/50 chance of extending the wrong one, and `planning.live_world_state`'s
`validate_live_world_state` function looks like it *should* be the admission gate for `live.world_state`
but is never called from `live/*` at all.

**Why it matters:** This is exactly the kind of ambiguity that compounds under real perception. When a
second engineer (or agent) adds fusion or identity-continuity logic, they need one obvious place to put
"canonical observed truth." Two similarly-named types with overlapping purpose is a standing invitation to
duplicate or diverge logic.

**Evidence:** `planning/live_world_state.py:58-110`, `live/world_state.py:54-109`, both test files above.

**Smallest correction:** Rename or explicitly deprecate one. If `planning.live_world_state` was an earlier
design sketch superseded by `live.world_state`, delete it or move it under `research/` per the repo's own
audit doc recommendation (§4 of `ATLAS_LIVE_REPOSITORY_AUDIT_2026-09-04.md`), and drop/rename its test.
Do not silently keep both — pick the canonical one now, before more logic accretes on either.

**Timing:** Now (it's a rename/deletion, near zero risk, and gets more confusing every sprint).

---

## 1. WORLD-STATE MODEL

### 1.1 IMPORTANT — Reconciler silently persists stale entities with no freshness signal

**Subsystem:** `live/world_state.py::LiveWorldStateReconciler.ingest`.

**Issue:** When an observation frame omits a previously-seen entity, the reconciler carries the entity
forward unchanged except for `confidence`/`last_observed_timestamp_ns` bookkeeping... but actually look
closer: the reconciled entity is only created from `obs` in the loop `for obs in frame.entities`. An entity
that is *not* present in the current frame is **not touched at all** — it just stays in `self._entities`
forever, at its last known pose/velocity, with its old `last_observed_timestamp_ns`, and is included in
every future `LiveWorldState` snapshot as if it were still valid. `LiveWorldState` and `LiveWorldEntity`
carry `last_observed_timestamp_ns` per entity, so staleness is *technically knowable*, but nothing in the
reconciler, event engine, or production layer ever checks it. A camera dropout on a player for 3 real
seconds produces a `LiveWorldState` that reports that player at his 3-second-old velocity, and the event
engine will happily run kinematic math (acceleration, proximity) against that stale pose as if it were
current.

**Why it matters:** This is precisely the "hidden prediction/extrapolation" case the review was asked to
hunt for — except it's not even explicit extrapolation, it's *silent state staleness masquerading as
current truth*. The snapshot doc's claim "Strict separation of observed state from predictions" is not
actually enforced by any check; it holds today only because the simulated provider always emits both
entities on every frame. The moment a real camera drops a track (occlusion, motion blur, provider hiccup —
completely normal in soccer), this assumption breaks invisibly.

**Evidence:** `live/world_state.py:166-208` (the reconciliation loop only updates entities present in
`frame.entities`; nothing marks or excludes absent ones); `LiveWorldEntity.last_observed_timestamp_ns` field
exists but is never read anywhere in `event_engine.py` or `production_intent.py`.

**Smallest correction:** Do not build a full staleness-decay system now. Add one explicit, cheap guard: expose
a `LiveWorldState.is_fresh(entity_id, now_ns, max_age_ns)` (or equivalent) and have `LiveEventEngine`
consult it before evaluating kinematics on an entity. This makes staleness an explicit, testable decision
instead of an implicit accident.

**Timing:** Before real perception. Simulated feeds don't drop entities; real cameras will, immediately.

### 1.2 SOUND — Derived velocity computation is appropriately scoped

`LiveWorldStateReconciler` deriving velocity from consecutive poses when the provider doesn't supply it
(`world_state.py:168-175`) is a reasonable, clearly-scoped piece of state reconciliation — it's finite
difference on two already-reconciled poses, not a filter or predictive model, and it correctly refuses to
compute across coordinate-frame mismatches (`if prior.pose.frame_id == obs.pose.frame_id`). This is the
right place for it: it's part of turning raw observations into a coherent snapshot, not semantic
interpretation. No action needed.

### 1.3 WATCH — LiveWorldState is a "last observation wins" model, not a filtered/estimated state

**Issue:** The reconciler has no filtering, smoothing, or outlier rejection of its own (that's delegated
upstream to `PerceptionAdapter`'s confidence/velocity-sanity gates). At single-provider, simulated-feed
scale this is fine and arguably correct (World-State should be "what we believe now," not a Kalman
estimate). But it means World-State's authority is only as good as whatever the single upstream adapter
already filtered — there's no state-level defense if perception ever double-reports, or if two providers
disagree. This is a legitimate future problem (multi-sensor fusion, section 4), not a defect today.

**Timing:** Defer. Correct to fix if/when a second synchronous provider is introduced (see 4.1).

---

## 2. TEMPORAL MODEL

### 2.1 SOUND — The six clock points are real, distinct, and actually preserved

Checked end-to-end: `sensor_timestamp_ns` → `timestamp_ns` is preserved unchanged from
`RawPerceptionFrame` through `LiveObservationFrame` → `LiveWorldState` → `LiveEvent` → `ProductionIntent`
(verified directly in `tests/test_live_perception_adapter.py::test_temporal_chain_preserves_physical_event_time...`).
`ingested_at_ns`, `reconciled_at_ns`, `detected_at_ns`, `created_at_ns` are each independently stamped with
`time.perf_counter_ns()` at the correct boundary and never fed back into physical-time fields. On the Unreal
side, `ReceiverCycles`/`ValidatedCycles`/`EnqueuedCycles`/`DequeuedCycles`/`DispatchedCycles` are recorded
with `FPlatformTime::Cycles64()` and never subtracted against the Python `perf_counter_ns()` domain
directly — cross-process latency is only ever computed within one clock domain at a time. This is a
genuinely well-executed separation and the strongest part of the architecture. No correction needed.

### 2.2 IMPORTANT — `perf_counter_ns()` is process-relative; multi-provider or multi-process deployment breaks it silently

**Issue:** All host-side monotonic stamps (`ingested_at_ns`, `reconciled_at_ns`, `detected_at_ns`,
`created_at_ns`) use `time.perf_counter_ns()`, which is explicitly documented by Python as having an
**arbitrary per-process reference point** — it is not comparable across processes, only within one. Today
everything (perception adapter, reconciler, event engine, decision layer) runs in one Python process, so
this is invisible. The moment perception ingestion is split into its own process (a very likely
architecture for a real camera/tracking SDK, e.g. a vendor SDK that must run in its own process/GIL-heavy
loop), any latency metric computed as `reconciled_at_ns - ingested_at_ns` becomes meaningless if those two
timestamps were taken in different processes.

**Why it matters:** Directly touches "multi-sensor operation" and "real perception" — a hardware tracking
SDK integration is one of the most likely reasons to run perception ingestion out-of-process (vendor SDK
threading model, crash isolation, GPU driver conflicts). The current temporal model's soundness (2.1)
quietly depends on single-process deployment, and that dependency is undocumented.

**Evidence:** `live/perception_adapter.py:157` (`time.perf_counter_ns()`), `world_state.py:207`,
`event_engine.py:181`, `production_intent.py:213` — all four host clocks use the same call, and the
architecture snapshot's temporal diagram (`ATLAS_LIVE_ARCHITECTURE_SNAPSHOT.md` §4) presents them as
though they compose correctly regardless of process boundary.

**Smallest correction:** Document the constraint explicitly now (perception ingestion, reconciliation, event
detection, and decision layer must currently share one process for `perf_counter_ns()` deltas to be valid).
Do not build cross-process clock sync yet — just make the constraint visible so nobody splits perception
into a subprocess and silently gets garbage latency telemetry.

**Timing:** Document now (cheap); solve for real only when a provider actually needs a separate process.

### 2.3 WATCH — No explicit epoch/wall-clock anchor for `sensor_timestamp_ns`

**Issue:** `sensor_timestamp_ns` is treated as an opaque monotonically increasing integer with no defined
epoch. That's fine for one provider. It becomes ambiguous the instant two providers (two cameras, or a
camera + a wearable/UWB tag) need to be reconciled against a shared physical instant — "5.0s discontinuity"
and monotonic-ordering checks are meaningless across providers with different epoch bases.

**Timing:** Defer — becomes relevant only when a second synchronous source exists (ties to 3.1/4.1).

---

## 3. PERCEPTION BOUNDARY

### 3.1 CRITICAL — Strict per-provider monotonicity in `PerceptionAdapter` cannot survive multi-provider fan-in without a redesign of *where* the check lives

**Subsystem:** `live/perception_adapter.py::PerceptionAdapter.process_raw_frame`.

**Issue:** `PerceptionAdapter` is documented and coded as accepting frames from a **single provider**
(`self.source_id`, one `_last_sensor_timestamp_ns` scalar, one `_last_known_positions` dict). The monotonic
check `raw.sensor_timestamp_ns < self._last_sensor_timestamp_ns` is adapter-instance state, so today one
`PerceptionAdapter` == one provider == one ordering domain, which is architecturally correct *as far as it
goes*. The problem is what happens next: two cameras at different frame rates (e.g. 50Hz and 120Hz) each
get their own `PerceptionAdapter` instance (correct), but there is currently **no defined component that
merges two adapters' output streams into one temporally-ordered stream feeding `LiveWorldStateReconciler`.**
`LiveWorldStateReconciler.ingest` itself also enforces its *own* strict frame-level monotonicity
(`frame.timestamp_ns <= self._last_observation_timestamp_ns: return None`) — one scalar, one ordering
domain, at the reconciler too. So today there are two consecutive single-stream monotonicity gates
(adapter, then reconciler), and multi-provider fan-in has no seam between them. If provider B's frame at
t=105ms arrives after provider A's frame at t=110ms has already been reconciled, the reconciler will
unconditionally drop B's t=105ms frame as stale — even though it's perfectly valid data that simply arrived
out of merge-order because of independent capture/encode latency. This isn't a hypothetical: the
architecture snapshot's own risk list explicitly names this ("Multi-Camera Asynchronous Arrival Jitter",
`ATLAS_LIVE_ARCHITECTURE_SNAPSHOT.md` §7.1) — but frames it as a future adapter enhancement, when actually
the fix belongs in a new component **between** adapters and the reconciler, not inside either.

**Why it matters:** This is the single most consequential finding for "toward... multi-sensor operation."
`allow_out_of_order=True` on the adapter (its stated escape hatch) doesn't fix this — it just stops the
*adapter* rejecting locally out-of-order frames from *its own* provider; it does nothing about the
reconciler's separate single-stream gate, and does nothing about *merging* two providers' streams into one
correctly-ordered sequence in the first place. Without an explicit reassembly/merge stage, adding a second
provider today would require either (a) feeding both providers through one shared adapter/reconciler
instance (breaks the "one provider, one ordering domain" invariant that makes today's monotonicity checks
sound), or (b) accepting that the reconciler drops any frame from the slower-arriving provider whenever the
faster one gets ahead.

**Evidence:** `perception_adapter.py:172-192` (single last-seen scalar); `world_state.py:154-155`
(reconciler's own independent single-scalar gate); `ATLAS_LIVE_ARCHITECTURE_SNAPSHOT.md:197-198`
acknowledges the gap but scopes the fix to "upstream of reconciliation" without naming a component.

**Smallest correction:** Do not build the fusion/reassembly layer now (that's section 4, correctly deferred).
But *do* name and reserve the seam: define that `LiveWorldStateReconciler.ingest` will eventually receive
frames from a merge/reassembly stage rather than directly from one adapter, and that reconciler-level strict
monotonicity is a single-source assumption that must move to (or be relaxed by) that merge stage, not be
solved by loosening `allow_out_of_order` on individual adapters. This is a documentation + interface-naming
correction, not an implementation.

**Timing:** Before multi-sensor work begins; not required before first real single-camera perception
integration, but must be resolved before a second concurrent source is added, and should be *decided in
principle* now so `allow_out_of_order` isn't mistakenly treated as "the" solution later.

### 3.2 IMPORTANT — `RawEntityMeasurement`/`RawPerceptionFrame` have no explicit provider capability/quality descriptor

**Issue:** The raw perception contract carries per-entity `confidence: float` and per-frame `source_id`, but
has no place for provider-level quality/capability metadata that real trackers commonly need to express:
detection vs. tracked vs. predicted-by-vendor, occlusion flag, calibration/frame validity, or camera
identity distinct from logical provider identity (a single tracking vendor may fuse 8 physical cameras
internally and report through one `source_id`). `attributes: Tuple[Tuple[str,str],...]` on both the
measurement and frame exists as a generic escape hatch, so this isn't a hard blocker — but nothing in
`PerceptionIngestionPolicy` or `PerceptionAdapter` reads or acts on any such flag today, and there's no
documented contract for what optional/required attribute keys real integrations should populate.

**Why it matters:** "Confidence/quality signals" was explicitly named as an audit target. A bare float
confidence is enough for the current single-rule ball-strike detector, but real vendor SDKs typically
report richer state (tracked/occluded/predicted/lost) that changes what a consumer should do — e.g. an
occluded-but-vendor-extrapolated position should probably not silently look identical to a genuinely
observed one to the event engine.

**Evidence:** `perception_adapter.py:36-48` (RawEntityMeasurement fields), no occlusion/tracking-state enum
anywhere in `live/*`.

**Smallest correction:** No schema change needed yet — just document the intended use of `attributes` for
this purpose (e.g. reserve a `track_state` attribute key) so the first real integration has a place to put
it without inventing a parallel channel.

**Timing:** Before real perception integration (cheap to specify now, expensive to retrofit after a vendor
integration already exists without it).

### 3.3 SOUND — RawPerceptionFrame/RawEntityMeasurement are appropriately provider-neutral and C++-portable

Plain, frozen dataclasses with primitive fields (str/float/int/tuple) — no Python-specific magic, no engine
types leaking in. This is a genuinely clean boundary for a future C++ reimplementation of the adapter: the
struct shape maps directly to a POD C++ struct. Good.

---

## 4. MULTI-SENSOR FUSION

### 4.1 IMPORTANT (documentation/decision, not implementation) — Fusion has no reserved seam distinct from reconciliation

Per instructions, no fusion design is proposed. But the review must determine "whether current interfaces
may prevent it" — and they do, mildly: `LiveWorldStateReconciler.ingest` takes exactly one
`LiveObservationFrame` at a time and treats "the frame that arrived" as authoritative for every entity it
contains, with last-write-wins semantics if two frames (from two providers) disagree about the same entity
in quick succession (whichever frame's timestamp is newer overwrites the previous entity state
unconditionally — `world_state.py:185-194`). There is no confidence-weighted merge, no per-source-priority
rule, nothing that would stop provider B's low-confidence guess from overwriting provider A's
high-confidence position simply because B's frame happened to have a later `timestamp_ns`. Today with one
provider this is invisible.

**Smallest correction:** As with 3.1, no fusion algorithm — just an explicit note (in
`ATLAS_LIVE_ARCHITECTURE_DIRECTION.md` or the snapshot) that `LiveWorldStateReconciler.ingest`'s current
per-entity overwrite rule is a single-source simplification, and that a fusion/reassembly layer sitting
*before* the reconciler (not inside it) is the intended seam — consistent with the repo's own direction doc
(§2-3 of `ATLAS_LIVE_ARCHITECTURE_DIRECTION.md`, which already gets this right in principle: "Do not treat
an external detector's output as Atlas truth"). The implementation hasn't yet caught up to that stated
principle for the multi-provider case.

**Timing:** Decision/documentation now; implementation deferred until a second live source exists.

### 4.2 SOUND — Observation vs. World-State split is the right foundation for fusion later

`EntityObservation` (raw, per-source) vs. `LiveWorldEntity` (reconciled, canonical) is exactly the
separation a fusion layer would need to slot into later — fusion consumes multiple `EntityObservation`
streams and produces the `LiveWorldEntity`. The type boundary is correct even though the reconciler's
internal merge policy (4.1) is currently naive.

---

## 5. EVENT ENGINE

### 5.1 IMPORTANT — `LiveEventEngine.evaluate` is structurally a single-event dispatcher, not a rule engine, and will not scale past a handful of hand-coded detectors

**Subsystem:** `live/event_engine.py::LiveEventEngine`.

**Issue:** `evaluate()` currently calls exactly one private method, `_detect_ball_strike`, hardcoded inline.
`EventType` already enumerates `POSSESSION_CHANGE`, `SHOT_ON_TARGET`, `BALL_OUT_OF_BOUNDS` — none of which
have any detector implemented. The moment those are added, the natural (and likely) path is: add
`_detect_possession_change`, `_detect_shot_on_target`, etc. as more private methods, each called
sequentially in `evaluate()`, each independently re-deriving kinematics (acceleration, proximity, direction)
from the same two `LiveWorldState` snapshots. There is no shared "kinematic feature" extraction step, no
rule registration mechanism, and no clear place to add cross-cutting concerns (e.g. cooldown/debounce so the
same physical strike doesn't fire two overlapping events, or event priority when two detectors fire on the
same tick). This is exactly the "accumulating collection of special cases" pattern the review was asked to
watch for — it hasn't accumulated yet only because there is currently one rule.

**Why it matters:** Tactical/semantic events (passes, possession phases, pressing triggers, offside-adjacent
geometry) are combinatorially richer than "ball accelerates near a player." Without a shared feature layer
or rule registration contract, each new event type will likely duplicate distance/velocity/acceleration
math and grow `evaluate()` into an if/elif ladder or a longer straight-line sequence of independent detector
calls with no shared state or lifecycle (e.g. multi-frame state machines for "possession phase," which
`evaluate()`'s two-snapshot signature `(current_state, prior_state)` cannot express — it has no memory
across more than one prior frame).

**Evidence:** `event_engine.py:97-109` (`evaluate` body is literally one `if` on one detector);
`EventType` enum already lists three undetected types (`event_engine.py:20-24`).

**Smallest correction:** Do not build a general rule engine now (explicitly out of scope — "do not design the
future fusion system unless necessary" applies equally here). But do the minimum structural change before a
second detector is added: give `LiveEventEngine` a small internal registry (`List[Callable[[current, prior],
Optional[LiveEvent]]]`) that `evaluate()` iterates, instead of hardcoding one call. This is a ~10-line
change that avoids the if/elif accretion pattern without building any speculative framework, and gives each
future detector an isolated, independently testable unit.

**Timing:** Before the second event type is implemented — cheap now, awkward to retrofit once 3-4 detector
methods already exist inline.

### 5.2 WATCH — Event engine has no multi-frame memory / state machine capability

**Issue:** `evaluate(current_state, prior_state)` only ever sees two consecutive snapshots. `BALL_STRIKE`
(an instantaneous kinematic discontinuity) fits this signature well. `POSSESSION_CHANGE` and tactical events
generally do not — they require tracking "who has had proximity+control for N consecutive frames," which
needs event-engine-owned state across many ticks, not just t-1/t. Today's `LiveEventEngine` has no per-tick
persistent state at all beyond a counter.

**Why it matters:** This is a real future rewrite risk, but it's reasonably foreseeable and shouldn't be
solved speculatively.

**Timing:** Defer — correct to add engine-owned rolling state only when the first multi-frame event type is
actually implemented.

### 5.3 IMPORTANT — Physical event detection and visual production are coupled through a single confidence gate, not through independent semantics

**Subsystem:** `live/production_intent.py::LiveProductionDecisionLayer.evaluate`.

**Issue:** The audit asks specifically to check for "coupling between physical event detection and visual
production." The type-level separation is good (`LiveEvent` has zero knowledge of `ProductionTreatment`).
But the *mapping function* itself is a single deterministic `if event.event_type.value == "ball_strike":
return ProductionIntent(...)` — one event type maps to exactly one treatment, one preset, with intensity
and duration derived by one fixed formula (`100 + event.intensity * 200`). There is no notion of context
(camera framing, whether an effect is already active, match phase, broadcast vs. highlight mode) affecting
the choice of treatment — which is fine for a vertical slice, but the *class* of design (a flat switch from
event type to a single hardcoded intent shape) is what will need to become a real decision surface once
"cinematic decision making" and multiple treatments per event type are wanted. Today's design isn't wrong,
but it will not "grow" into the target state — it will need to be replaced, not extended, and the earlier
this is anticipated the smaller the eventual change.

**Evidence:** `production_intent.py:198-216`.

**Smallest correction:** None needed today — flag as a known, bounded future replacement rather than an
extension point. Do not add a rules engine, plugin registry, or config-driven mapping table now; there is
only one rule, and premature generality here is exactly the anti-pattern the direction doc warns against
(§16: "giant generalized plugin frameworks before a second integration exists").

**Timing:** Defer — revisit when a second event type needs a production mapping, at which point the shape
of the real decision surface will be informed by two concrete cases instead of speculation.

---

## 6. PRODUCTION INTENT

### 6.1 IMPORTANT — `parameters: Mapping[str, Any]` is already lossy across the process boundary, and nothing prevents it becoming an uncontrolled schema escape hatch

**Subsystem:** `live/production_intent.py::ProductionIntent.parameters`; Unreal-side
`AtlasLiveTcpListener::ParseAndValidateEnvelope`.

**Issue:** Python-side, `parameters` is `Optional[Mapping[str, Any]]` — genuinely `Any`, frozen via
`_freeze()` but not schema-checked. On the wire it's serialized as JSON (arbitrary nesting, arbitrary
value types). On the Unreal receiving side, `AtlasLiveTcpListener::ParseAndValidateEnvelope` reads
`Parameters` into a flat `TMap<FString, FString>` and does `Pair.Value->AsString()` unconditionally
(`AtlasLiveTcpListener.cpp:497-505`). This means: (a) any non-string parameter value (a number, bool, nested
object/array) sent from Python is silently coerced to Unreal's string representation of that JSON value with
no validation and no error surfaced anywhere, and (b) there is no schema, allow-list, or versioning for what
keys `parameters` may legitimately contain — today it holds exactly one key (`preset`) by convention only.
`test_tcp_frame_oversized_rejection` even demonstrates the pattern by stuffing 70 arbitrary string keys into
`parameters` to blow the 64KB frame ceiling — proving the field already behaves as an unbounded bag, not a
constrained contract.

**Why it matters:** This is precisely the risk named in the prompt: "creative extension point vs.
uncontrolled schema escape hatch." Two failure modes are already latent: (1) silent type coercion on the C++
side means a Python-side bug (e.g. sending `intensity_multiplier: 1.5` as a float parameter) fails
*silently* as a stringified value with no error, not loudly; (2) with no schema or key registry, nothing
stops different treatments/presets from inventing incompatible parameter shapes over time, and nothing
detects drift between what Python sends and what a given Unreal handler actually reads (currently only
`preset` is read by `FAtlasLiveEffectRegistry::DispatchIntent`; every other key is parsed into `Parameters`
but consumed by no handler at all).

**Evidence:** `production_intent.py:49,75-78`; `AtlasLiveTcpListener.cpp:497-505` (unconditional
`AsString()`); `AtlasLiveEffectRegistry.cpp:134-138` (only `preset` is ever read); `test_live_tcp_transport.py:41-48`.

**Smallest correction:** Do not add a generalized schema/validation framework now (one key is in active use).
Do the minimum: (1) document that `parameters` values are lossily coerced to strings across the Unreal
boundary today, so nobody sends structured/numeric parameters expecting fidelity; (2) when a second
parameter key is actually needed by a real handler, that is the trigger to introduce either typed
sub-fields on `ProductionIntent` for well-known creative knobs (e.g. `preset: str` promoted to a first-class
field) or an explicit value-type tag on the wire — decide then, informed by what the second real use case
needs, not now.

**Timing:** Document the coercion behavior now (near-zero cost); defer schema design until a second
parameter key is genuinely required — do not design it speculatively.

### 6.2 WATCH — `treatment`/`preset` split is a two-level enum-plus-string-key scheme without a defined relationship contract

**Issue:** `treatment` is a closed Python enum mirrored by a closed C++ enum (`EAtlasLiveTreatment`) that
must be kept in manual sync (`ProductionTreatment` in `production_intent.py:27-33` vs. the string-match
ladder in `AtlasLiveTcpListener.cpp:446-451`) — adding a treatment requires editing both languages by hand
with no shared source of truth or generation step, and a mismatch fails silently to `EAtlasLiveTreatment::Unknown`
(which then fails "missing preset" downstream, not a decode error). `preset` is a free string
looked up via `FAtlasLiveEffectRegistry::FindHandler` with a treatment+preset composite key
(`AtlasLiveEffectRegistry.cpp:29-32`). This two-level scheme (closed enum, open string) is reasonable
today, but the enum mirroring is a manual-sync liability that will silently degrade to `Unknown` rather
than erroring loudly on mismatch.

**Timing:** Defer — becomes worth fixing once treatment additions become frequent enough that manual
enum sync causes an actual incident; not urgent at one-treatment-active scale.

### 6.3 SOUND — Envelope digesting and `to_dict`/`from_dict` round-tripping is a genuinely engine-neutral, versioned contract

The `ProductionIntentEnvelope` digest scheme, the explicit protocol version byte, and the fact that
`ProductionIntent` has zero Unreal-side imports are real strengths — this part of the design matches its
stated goal.

---

## 7. PYTHON/C++ BOUNDARY

### 7.1 SOUND — Perception ingestion is the cleanest, lowest-risk native migration candidate, and the interfaces already support it

`RawPerceptionFrame`/`RawEntityMeasurement` are plain, primitive-typed, frozen structs with no Python
runtime dependency in their *shape* (confirmed in 3.3). `PerceptionIngestionPolicy` is pure numeric
threshold logic. This is a legitimately clean boundary — a C++ reimplementation could consume the same
wire/struct shape with no architectural rework, only when profiling actually demands it (per the direction
doc's own non-goal list, "no speculative C++ rewrites"). No correction needed; this is correctly identified
in the snapshot doc's migration table (§6) and the implementation backs up that claim.

### 7.2 WATCH — World-State reconciliation's Python-object identity (`Dict[str, LiveWorldEntity]`, immutable dataclasses) will need a real interface contract before any C++ replacement, not just a data-shape match

**Issue:** Unlike perception ingestion, `LiveWorldStateReconciler` isn't just transformng flat data — it
mutates instance dictionaries (`self._entities`), owns a bounded history list, and returns fully-formed
frozen dataclass snapshots that Python code elsewhere (event engine, tests) call methods on
(`state.has_entity(...)`, `state.entity(...)`). A C++ reimplementation would need to either replicate this
object-with-methods ergonomic (awkward from C++, or via a thin Python wrapper over a C++ core) or the calling
code (event engine, tests, runtime coordinator) would need to change. This is a real but not urgent
migration cost — flagged as WATCH because it doesn't block anything today, but the interface's current
shape (methods on the returned snapshot) is more coupled to "being a Python object" than
`RawPerceptionFrame` is.

**Timing:** Defer until reconciliation is actually a profiling bottleneck (per the direction doc's own
rule — let measurement drive native migration, not preference).

### 7.3 SOUND — Event engine and decision layer are appropriately kept in Python for now, and their eventual C++ migration path is not blocked

Both are pure functions over already-reconciled state with no I/O; nothing about their current shape
prevents a later native rewrite once/if profiling demands it. No correction needed.

---

## 8. UNREAL BOUNDARY

### 8.1 SOUND — Unreal is genuinely treated as execution-only, not semantic truth

Verified directly in the C++: `FAtlasLiveEffectRegistry` and its handlers only ever *read* intent fields to
decide visual parameters (light intensity, post-process contrast, line length) — nothing in the reviewed
Unreal code writes back to Python, computes a semantic decision, or originates a `ProductionIntent`. The
`atlas_entity:<ID>` actor tag lookup (`FindTargetActor`) is a pure resolution step, not a truth source. This
matches the intended boundary and the architecture snapshot's claim. No correction needed.

### 8.2 IMPORTANT — Visual deadline enforcement only fires if `ReceiverCycles` is nonzero, silently skipping the deadline check for any intent that arrives without it

**Subsystem:** `AtlasLiveEffectRegistry.cpp::DispatchIntent`.

**Issue:** `if (Intent.ReceiverCycles > 0) { ...deadline check... }` — deadline enforcement is
conditional on the receiver having stamped `ReceiverCycles`. `ReceiverCycles` is only stamped by
`FAtlasLiveTcpListener::ProcessClientStream` (`AtlasLiveTcpListener.cpp:274,342`). Any intent constructed and
dispatched through a path that doesn't go through the real TCP listener (unit tests constructing
`FAtlasLiveProductionIntent` directly, or a future alternate transport such as shared memory or in-process
delivery) silently bypasses the deadline check entirely rather than failing safe. `AtlasLiveIngressQueueTest.cpp`'s
`MakeTestIntent` helper never sets `ReceiverCycles`, so the entire ingress-queue and pump test suite
exercises code paths where deadline enforcement is structurally impossible to trigger — a gap the current
test suite doesn't surface because it never needs to.

**Why it matters:** "Expired visual deadlines" is one of the explicit real-time failure modes the review
was asked to audit, and the mechanism that enforces it degrades by *omission* rather than by an explicit,
observable decision. A future alternate transport (the snapshot doc explicitly floats shared-memory/named-pipe
alternatives in the transport benchmark) that doesn't populate `ReceiverCycles` would silently disable
deadline enforcement with no warning, log, or telemetry signal.

**Evidence:** `AtlasLiveEffectRegistry.cpp:120-131`; `AtlasLiveTcpListener.cpp:274`;
`AtlasLiveIngressQueueTest.cpp:15-33` (`MakeTestIntent` never sets `ReceiverCycles`).

**Smallest correction:** Invert the guard: treat `ReceiverCycles == 0` as "deadline unknown, enforce
conservatively" (either reject, or log a warning telemetry counter) rather than "skip the check." This is a
few-line change, not a redesign.

**Timing:** Before production-scale Live development — not blocking for the current single-transport
vertical slice, but should not ship silently into a second transport implementation.

### 8.3 WATCH — `FindTargetActor` does a linear `TActorIterator` scan of the entire world per intent

**Issue:** `FAtlasLiveEffectRegistry::FindTargetActor` (`AtlasLiveEffectRegistry.cpp:74-109`) iterates every
actor in the world on every dispatch to find a tag match, with no cache. At vertical-slice scale (few
actors, low intent rate) this is invisible. At real broadcast scale (many actors: full 22 players + ball +
cameras + set dressing, at higher intent rates once tactical/cinematic events are added) this becomes a
real per-tick cost on the GameThread — the exact resource the pump/queue design otherwise carefully
protects (bounded batch size, non-blocking queue). It's an internal inconsistency: significant engineering
went into bounding queue/pump costs, but the effect dispatch step it feeds still does an unbounded linear
world scan.

**Timing:** Defer — correct to fix (e.g. an entity-id → actor cache invalidated on spawn/destroy) once actor
counts or intent rates are large enough to matter; premature to build now on a vertical slice with a
handful of actors.

### 8.4 SOUND — Ingress queue overflow, dedup, and session-reset behavior is deterministic and well-tested

`FAtlasLiveIngressQueue`'s drop-oldest overflow, sliding-window dedup, and per-session monotonic sequence
enforcement are implemented straightforwardly and covered by real concurrency tests (MPSC producer test in
`AtlasLiveIngressQueueTest.cpp`). This is a case where the tests actually do exercise the contract, not just
the implementation. No correction needed.

---

## 9. IDENTITY CONTINUITY

### 9.1 CRITICAL — `atlas_entity:<ID>` is a bare string match with no reconciliation boundary, and the failure mode on ID churn is silent, not observable

**Subsystem:** Cross-cutting: `live/production_intent.py` (`target_entity_ids: Tuple[str,...]`),
`AtlasLiveEffectRegistry::FindTargetActor` (tag string match), and the complete absence of any identity
layer between perception-assigned tracking IDs and `atlas_entity:<ID>` tags.

**Issue:** The entire identity chain from raw perception to Unreal actor resolution is: whatever string a
provider calls an entity (`RawEntityMeasurement.entity_id`) flows unchanged through observation, world-state,
event, and intent, and is finally string-matched against a Unreal actor tag. There is no identity
reconciliation layer anywhere in the reviewed code — contrast with `planning/digital_twin_identity.py`,
which the *rest* of Atlas already has (`evaluate_identity`, `IdentityMatchStatus.MATCH/NO_MATCH/INSUFFICIENT_EVIDENCE`,
explicit required-anchor semantics) for the offline Digital Twin, but which Live's perception path does not
use or reference at all. When a real tracker drops a player's track and reassigns a new tracking ID mid-play
(normal behavior for every commercial tracking vendor after occlusion), Atlas Live has no concept that
"player-09" and "player-47" might be the same physical entity — it will simply stop being able to resolve
"player-09" (silently failing `MissingTarget` in the effect registry, per the snapshot doc's own §7.3) and
start treating "player-47" as an entirely new entity with no history, no confidence carry-over, and no
world-state continuity. The failure is *architecturally correct to fail* (the review explicitly says not to
build identity fusion now) — but the review also asks whether the failure is deterministic and *observable*,
and today it is not clearly observable: `MissingTarget` telemetry exists on the Unreal side
(`FAtlasLiveEffectTelemetry.TotalMissingTarget`), but nothing on the Python side (world-state, event engine)
has any signal that an entity_id that used to resolve now silently doesn't, or that it might be the same
physical entity under a new ID. From World-State's perspective, "player-09 stopped appearing" and "player-09
was renamed player-47" are indistinguishable events, and neither produces any explicit signal.

**Why it matters:** This is the single most consequential *near-term* problem for real perception, because
ID churn is not a hypothetical multi-sensor-future concern — it happens on **every single-camera tracker**
in normal soccer play (occlusion during a tackle, players bunching up, re-entry from off-frame). The current
architecture is correctly scoped to not solve fusion/re-identification now, but it has not yet even named the
seam where a future "tracking ID → stable Atlas entity identity" resolver would live. Today that
resolution, if it existed, would have to sit between `PerceptionAdapter` and `LiveWorldStateReconciler` (or
inside a new component) — but nothing marks that as a reserved boundary, and the existing
`digital_twin_identity.py` machinery (which already models exactly this kind of "insufficient evidence to
merge safely" decision) is not referenced, reused, or even discussed in any Live doc.

**Evidence:** No identity-resolution code path exists between `perception_adapter.py` and `world_state.py`;
`planning/digital_twin_identity.py` exists with directly relevant machinery and is unused by `live/*`;
`ATLAS_LIVE_ARCHITECTURE_SNAPSHOT.md` §7.3 names the symptom (`MissingTarget`) but not a resolution boundary.

**Smallest correction:** Do not build tracking-ID fusion now (explicitly out of scope per the prompt). Do
name and reserve the boundary: document that a future "entity identity resolver" sits between
`PerceptionAdapter`/fusion output and `LiveWorldStateReconciler`, is responsible for mapping potentially
churning provider tracking IDs to stable Atlas entity identities, and should likely reuse or extend
`planning/digital_twin_identity.py`'s MATCH/NO_MATCH/INSUFFICIENT_EVIDENCE model rather than inventing a
parallel one. Additionally, surface entity presence/absence transitions as an explicit, observable
world-state-level signal (even just a telemetry counter: "entity X present in previous state, absent in
current state") so at minimum ID churn is *diagnosable* from logs even before it's *solved*.

**Timing:** Document the reserved boundary now (near-zero cost, prevents duplicate/incompatible identity
logic from being invented ad hoc later); implement resolution only when real perception makes ID churn an
observed, not theoretical, problem — likely very early in real integration, given how common occlusion is.

---

## 10. REAL-TIME FAILURE MODES

### 10.1 SOUND — Most failure modes are deterministic, bounded, and telemetry-visible

Verified concretely: stale/out-of-order observations (adapter + reconciler, both reject deterministically
with typed rejection reasons and counters), queue overflow (drop-oldest with counter), transport disconnect
(explicit `ConnectionState` machine, clean socket teardown), reconnect (session ID re-anchoring, sequence
domain reset, `TotalReconnectsCount`), duplicate intents (sliding-window dedup with counter), malformed/oversized
frames (rejected pre-queue with counters), digest failure (rejected with counter). This is a genuinely
strong list of deterministic, observable degradation paths, and it is one of the better-executed aspects of
the system. This finding class is explicitly excluded from CRITICAL/IMPORTANT because it's already sound —
noted here as the counterweight to the failure modes below that are *not* yet observable.

### 10.2 IMPORTANT — GameThread stalls degrade by silent eviction with no health signal surfaced back to Python

**Issue:** The snapshot doc names this directly (§7.2): under GameThread hitching, fresh intents evict
stale queued ones. This is a reasonable *design* choice (visual freshness over historical replay), but the
review asks whether degradation is *observable*, not just deterministic. `FAtlasLiveIngressQueue`'s
telemetry (`UtilizationRatio`, `bWarningThresholdExceeded`, `TotalDroppedOverflowCount`) exists entirely
Unreal-side, with **no path back to Python**. Python (the decision-making side that could, e.g., throttle
intent generation or alert an operator) has no visibility at all into Unreal-side backpressure — it will
keep generating and sending intents at full rate into a system that's already silently dropping them, with
`TcpTransportChannel.send()` reporting `DELIVERED` (a successful `sendall()`) even while the Unreal-side
queue is actively evicting.

**Why it matters:** "Delayed intents," "queue overflow," and "GameThread stalls" were named explicitly as
audit targets, and the gap here is specifically that the *Python* side — the side an operator or an eventual
cinematic-intelligence layer would actually act on — has zero feedback loop. `DeliveryStatus.DELIVERED`
on the Python side currently means "the OS accepted the bytes into the TCP send buffer," not "Unreal
processed it," which is a meaningfully weaker guarantee than the enum name suggests.

**Evidence:** `tcp_transport.py:184-193` (`DELIVERED` set immediately after `sendall()` succeeds, no
acknowledgment protocol); `AtlasLiveIngressQueue.h:66-82` (telemetry struct, Unreal-only, no export path);
no telemetry-pull mechanism from Python to Unreal anywhere in the reviewed code.

**Smallest correction:** No new subsystem needed — this is a real correction, not a deferral, but a small
one: either (a) document explicitly that `DeliveryStatus.DELIVERED` means "sent," not "processed," so nobody
downstream mistakes it for an execution guarantee, or (b) if operator-facing backpressure visibility is
wanted soon, add a lightweight periodic telemetry pull/push (even a simple side-channel poll) before scaling
intent volume. At minimum, the naming/documentation gap should be closed now.

**Timing:** Documentation correction now; a real feedback channel before production-scale Live development
(i.e., before intent volume is high enough that silent eviction actually starts happening in practice).

### 10.3 WATCH — No end-to-end idempotency guarantee if the same physical event is detected twice across a reconnect

**Issue:** `intent_id` is a simple incrementing counter per `LiveProductionDecisionLayer` instance
(`intent-0001`, `intent-0002`, ...). If the Python process restarts (e.g. after a crash) mid-match, the
counter resets, and a re-emitted `intent-0001` could theoretically collide with the dedup window on the
Unreal side if that ID is still within the sliding dedup window — or, more likely, simply *not* collide
(because the dedup window is bounded and time-limited) and be treated as a fresh, valid intent even if it
duplicates a previously-dispatched visual effect. This is a low-probability, low-severity scenario at
current scale.

**Timing:** Defer — acceptable for now; revisit if Python-side process restarts during live operation become
a real operational concern.

---

## 11. TEST ARCHITECTURE

### 11.1 IMPORTANT — Tests prove today's single-path contracts well, but there is no test anywhere that exercises entity absence, staleness, or ID churn

**Issue:** The 51 passing Python tests are genuinely good at what they cover: temporal separation
(`test_temporal_chain_preserves_physical_event_time...`), rejection policies (out-of-order, stale,
discontinuity, confidence, velocity), transport framing/digest/disconnection, and one full vertical-slice
run. But — directly tied to findings 1.1 and 9.1 — there is no test anywhere in `tests/test_live_*.py` that
feeds the reconciler a frame *missing* a previously-seen entity and asserts what `LiveWorldState` should do
about it. There is no test exercising an entity_id that appears in one frame under one ID and needs to be
recognized as "possibly the same entity" (there's no code to test, which is itself the finding). This isn't
a call for a "massive test suite" — it's that the single most likely early real-perception failure (dropped
track / reassigned ID) has zero test coverage because there's no defined behavior to assert.

**Smallest correction:** Once finding 1.1's staleness guard is added, add exactly one test: reconciler
ingests frame A with two entities, then frame B with only one, assert on the resulting state's staleness
signal for the dropped entity. One test, not a suite.

**Timing:** Add alongside the 1.1 fix — small, targeted, not urgent enough to block anything currently
planned, but should land in the same change as the staleness guard.

### 11.2 WATCH — The four Unreal automation tests and several Python "proof" tests require live UnrealEditor-Cmd + real TCP port 7778, making them environment-coupled rather than hermetic

**Issue:** `test_live_perception_e2e_proof.py`, `test_live_tcp_e2e_proof.py`, `test_live_vfx_pipeline_proof.py`,
and `test_live_unreal_production_artifact_proof.py` all shell out to a hardcoded absolute path
(`C:/Program Files/Epic Games/UE_5.6/...`, `C:/Users/Gavin's PC/Desktop/Atlas/...`) and a hardcoded port
(7778), with up to 15s startup polling. These are valuable as *integration proofs* (and this review does not
recommend removing them), but they are not portable CI tests — they will not run on any machine without that
exact UE install path and will flake under port contention or slow CI hosts. This is a "proof it worked
once, here, on this machine" test class, not a regression-safety-net class.

**Timing:** Defer — acceptable for a single-developer vertical-slice phase; worth revisiting (parameterize
the path, use a dynamic port, or separate "manual proof" from "CI-safe" test tiers) before this becomes a
team-scale or CI-gated project.

---

## 12. LONG-TERM ATLAS ARCHITECTURE

Cross-referencing the ten findings above against the stated long-term target, the decisions most likely to
force a **major** (not incremental) rewrite, ranked:

1. **Entity identity continuity (9.1).** Every other layer (world-state, event engine, production intent,
   Unreal tag resolution) currently assumes `entity_id` is a stable, permanent key. Real perception will
   violate that assumption immediately and continuously. This is the finding most likely to force rework of
   multiple layers at once if not addressed with at least a reserved boundary soon.
2. **Multi-provider frame merge (3.1/4.1).** Two independent single-stream monotonicity gates (adapter,
   reconciler) with no merge seam between them means the first second-provider integration will require
   real interface surgery, not just an additive component, unless the seam is reserved now.
3. **Event engine's two-snapshot signature (5.2).** Tactical/possession-style events need multi-frame memory
   the current `evaluate(current, prior)` contract cannot express. This is foreseeable now and cheap to keep
   in mind, expensive to retrofit after 5+ detector methods exist.
4. **`parameters: Mapping[str, Any]` lossy coercion (6.1).** Not a rewrite risk by itself, but a silent
   correctness trap that will produce confusing bugs (silently stringified values) as more treatments are
   added, well before it forces any structural change.
5. **Two parallel `LiveWorldState` implementations (finding 0).** Not a technical rewrite risk, but a
   process/clarity risk that compounds with every sprint it's left unresolved.

Decisions that are **appropriately deferred** and should **not** be touched now: fusion algorithm design,
prediction/extrapolation, event-engine rule framework, production-intent schema generalization, C++
migration of anything, GameThread actor-lookup caching, cross-process clock synchronization. All of these
are correctly out of scope for the current maturity level and building them now would violate the
project's own stated anti-patterns (`ATLAS_LIVE_ARCHITECTURE_DIRECTION.md` §16).

---

## Summary

### A. Overall architecture assessment

The core pipeline shape (Observation → World-State → Event → Intent → Transport → Unreal execution) is
sound and the boundaries are, for the most part, honestly drawn — Unreal genuinely has no semantic
authority, physical time and processing time are genuinely kept separate, and the perception contract is
genuinely provider-neutral in its data shape. The implementation is unusually disciplined about *not*
smuggling logic across boundaries (no hidden prediction in world-state, no event detection in Unreal, no
UObjects in the intent contract). Where the architecture is weaker is not in what it does, but in what it
has not yet named: there is no reserved seam for multi-provider frame merging, no reserved seam for entity
identity continuity, and two competing implementations of the same concept ("LiveWorldState") coexist
unresolved. These are gaps of omission in an otherwise careful design, not signs of an unsound design.

### B. Top 5 risks

1. Entity identity continuity has no reserved architectural boundary (9.1) — the most likely near-term
   real-perception breakage.
2. Multi-provider frame ordering has two independent single-stream gates and no merge seam (3.1/4.1).
3. World-state silently carries stale/absent entities forward with no freshness check anywhere downstream
   (1.1).
4. Event engine is structurally a one-rule dispatcher that will accrete special cases without a tiny
   registration change (5.1).
5. `parameters: Mapping[str, Any]` already loses type fidelity across the Unreal boundary silently (6.1).

### C. What should be changed before real perception

- Add an explicit staleness signal on world-state entities and have the event engine consult it (1.1).
- Document (not implement) the reserved multi-provider merge seam and its relationship to
  adapter/reconciler monotonicity (3.1).
- Document the reserved entity-identity-resolution boundary and point it at
  `planning/digital_twin_identity.py`'s existing MATCH/NO_MATCH model instead of letting a parallel scheme
  get invented later (9.1).
- Resolve the two competing `LiveWorldState` implementations — delete or clearly deprecate one (finding 0).
- Document the `perf_counter_ns()` single-process constraint on the temporal model (2.2).
- Document the `parameters` lossy string-coercion behavior on the Unreal boundary (6.1).
- Give `LiveEventEngine.evaluate` a trivial internal detector list instead of one hardcoded call, before a
  second event type is implemented (5.1).
- Invert the `ReceiverCycles > 0` deadline-check guard so missing timestamps fail conservative, not silent
  (8.2).

None of these require new frameworks, new subsystems, or fixes to what's already built — they are
documentation, a couple of small guards, and one deletion/rename.

### D. What should explicitly NOT be changed yet

- Multi-sensor fusion algorithm design.
- Prediction/extrapolation of any kind.
- A generalized event rule engine or plugin framework.
- Schema/versioning framework for `ProductionIntent.parameters`.
- Any C++ migration of perception, world-state, or event engine — none are profiling-justified yet.
- GameThread actor-lookup caching in the effect registry.
- Cross-process clock synchronization for `perf_counter_ns()`.
- Making the "proof" integration tests hermetic/CI-portable.
- A Python-to-Unreal backpressure feedback channel (documentation of the `DELIVERED` semantics gap is
  enough for now; the channel itself can wait).

### E. Does the Architecture Snapshot accurately represent the implementation?

Mostly yes, with two gaps. It accurately describes the pipeline shape, the temporal model, the wire
protocol, and the Unreal ingress/dispatch mechanics — these all check out against the code as written. It
under-states two things: (1) the "Multi-Camera Asynchronous Arrival Jitter" risk (§7.1) is framed as a
future adapter enhancement, when the actual gap spans both the adapter *and* the reconciler and needs a new
component, not an adapter tweak (finding 3.1); (2) it does not mention the entity-identity-continuity gap's
architectural depth at all beyond naming the `MissingTarget` symptom (§7.3) — it doesn't connect it to the
existing, directly-relevant `digital_twin_identity.py` machinery elsewhere in the repo, which a snapshot
aimed at external review should surface.

### F. Is Atlas Live ready to proceed toward real perception after this review?

Yes, conditionally. The vertical slice is a legitimate foundation and none of the CRITICAL findings require
new subsystems — they require documentation, one deletion, and a small number of narrow guards, all of
which are cheap relative to the value of not discovering them mid-integration with a real camera feed. The
recommendation is: make the changes in section C (all small), then proceed to a single real, single-camera
perception integration next — not multi-sensor, not prediction, not tactical events — exactly as the
project's own direction document already recommends. The identity-continuity and multi-provider-seam
findings should be *named and reserved* before that integration, not necessarily *solved*; they will become
urgent the moment a second provider or a real occlusion event actually occurs, which will likely be within
the first real integration attempt for identity continuity specifically.

### G. Escalation recommendation

One finding is worth a second opinion from a higher-capability model or a second human architect before
committing to a direction: the **entity identity continuity boundary (9.1)**, specifically whether it should
reuse `planning/digital_twin_identity.py`'s MATCH/NO_MATCH/INSUFFICIENT_EVIDENCE model or whether Live's
real-time constraints (no latency budget for a full identity evaluation per frame) require a distinct,
faster-path design that only escalates to the heavier offline-style identity model on ambiguous cases. This
is a genuine design fork with real long-term cost either way, and it's the one place in this review where
"the smallest reasonable correction" for *today* (just reserve the boundary) is clearly insufficient for
guiding the *actual* design decision that will need to be made soon after. Everything else in this review
is either already correctly resolved or small enough to fix without additional expert input.
