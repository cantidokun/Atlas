"""Milestone 6 deterministic fault-injection and concurrency test suite.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md
§31 (Required Deterministic Tests) and §32 (Required C++ Unreal Automation Tests).

Test modules and the contract matrix items they validate:

- test_m6_01_record_store_recovery ... §31 items 1,2,3,4,6,16,21
- test_m6_02_journal_faults ........... §31 items 7,8,9,10,11,17
- test_m6_03_submission_durable_intent. §31 items 5,18,22,23
- test_m6_04_receipt_crash_fencing ..... §31 items 19,20 + receipt identity conflicts
- test_m6_05_artifacts_verification .... §31 items 12,13,14,15 + artifact/what topology
- test_m6_06_concurrency_stability ..... §31 items 3,24,25 + concurrency/quiescence/rogue

Every test is deterministic: failures are injected via controlled fakes, scripted
responses, deterministic filesystem fixtures, and explicit concurrency primitives.
No live Unreal transport, no real process crashes, no timing sleeps.
"""