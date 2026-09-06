"""M8 — Witness Attestation + Engine Attempt Identity.

Deterministic tests for Contract V1 canonical HMAC-SHA256 journal attestation and
engine-side attempt_ordinal threading.

Requirements covered (G.1-G.16):
 1. attempt_ordinal transported correctly
 2. engine state retains attempt_ordinal
 3. journal retains attempt_ordinal
 4. reconciliation exposes attempt_ordinal
 5. mismatched attempt_ordinal fails closed
 6. exact HMAC conformance vector
 7. wrong nonce fails
 8. modified signed field fails
 9. missing HMAC fails
10. malformed HMAC fails
11. malformed canonical payload fails
12. plaintext nonce never appears in journal
13. plaintext nonce never appears in receipt
14. plaintext nonce never appears in manifest
15. valid attested journal continues through independent verification
16. invalid attested journal cannot produce verified evidence/receipt

Also covers Requirement E (secret handling) and Requirement C (conformance vector).
"""
import datetime
import json
import pathlib
import tempfile

import pytest

from planning.unreal_journal_attestation import (
    canonical_attestation_payload,
    compute_attestation_digest,
    compute_journal_attestation_digest,
    _SIGNED_FIELDS,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
import tests.m6.fault_fixtures as ff


# Fixed, deterministic conformance vector (Requirement C). This EXACT payload must
# produce EXPECTED_CANONICAL_HEX bytes and EXPECTED_DIGEST; the C++ automation test
# FAtlasUE56JournalAttestationVectorTest reproduces both identically.
CONFORMANCE_NONCE = "m8-nonce-0123456789abcdef0123456789abcdef"
CONFORMANCE_PAYLOAD = {
    "schema_version": 1,
    "atlas_job_id": "atlas-render-job-aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "unreal_job_id": "unreal-job-m8-001",
    "attempt_ordinal": 1,
    "phase": "FINISHED",
    "phase_sequence": 3,
    "editor_session_id": "session-m8-editor",
    "process_creation_time_utc": "2026-09-06T00:00:00Z",
    "output_directory": "C:/renders/out",
    "output_manifest": [{"path": "C:/renders/out/f.png", "size": 42, "sha256": "a" * 64}],
}
# Canonical bytes: `1\x1fatlas-render-job-aaaa-bbbb-cccc-dddd-eeeeeeeeeeee\x1f`
# `unreal-job-m8-001\x1f1\x1fFINISHED\x1f3\x1fsession-m8-editor\x1f`
# `2026-09-06T00:00:00Z\x1fC:/renders/out\x1fC:/renders/out/f.png\x1c42\x1c` + 64 a's
# `\x1d\x1e`  — i.e. field(sep)* + manifest entries + trailing record separator.
EXPECTED_CANONICAL_HEX = (
    "311f61746c61732d72656e6465722d6a6f622d616161612d626262622d636363"
    "632d646464642d6565656565656565656565651f756e7265616c2d6a6f622d6d"
    "382d3030311f311f46494e49534845441f331f73657373696f6e2d6d382d6564"
    "69746f721f323032362d30392d30365430303a30303a30305a1f433a2f72656e"
    "646572732f6f75741f433a2f72656e646572732f6f75742f662e706e671c3432"
    "1c61616161616161616161616161616161616161616161616161616161616161"
    "6161616161616161616161616161616161616161616161616161616161616161"
    "611d1e"
)
EXPECTED_DIGEST = "af7c077a395b80064537304447f4ae77fc9204577fdb70ec0189e30682288232"


# ── C. Conformance vector ────────────────────────────────────────────────────
def test_m8_c_conformance_vector_digest_is_fixed():
    assert compute_journal_attestation_digest(CONFORMANCE_NONCE, CONFORMANCE_PAYLOAD) == EXPECTED_DIGEST


def test_m8_c_conformance_server():
    msg = canonical_attestation_payload(CONFORMANCE_PAYLOAD)
    assert msg == bytes.fromhex(EXPECTED_CANONICAL_HEX)


def test_m8_c_conformance_independent_rfc2104_matches_stdlib():
    # Prove the C++ RFC-2104 algorithm (manual ipad/opad blocks over SHA-256)
    # produces the identical digest to the stdlib hmac — this is the contract
    # C++ ComputeJournalAttestationDigest must satisfy byte-for-byte.
    import hashlib as _hl

    def manual_hmac(key, message, block_size=64):
        if len(key) > block_size:
            key = _hl.sha256(key).digest()
        key = key.ljust(block_size, b"\x00")
        inner = _hl.sha256(bytes(k ^ 0x36 for k in key) + message).digest()
        outer = _hl.sha256(bytes(k ^ 0x5c for k in key) + inner).digest()
        return outer

    msg = canonical_attestation_payload(CONFORMANCE_PAYLOAD)
    assert manual_hmac(CONFORMANCE_NONCE.encode(), msg).hex() == EXPECTED_DIGEST


def test_m8_c_conformance_signed_field_order_is_fixed():
    assert _SIGNED_FIELDS == (
        "schema_version", "atlas_job_id", "unreal_job_id", "attempt_ordinal",
        "phase", "phase_sequence", "editor_session_id", "process_creation_time_utc",
        "output_directory", "output_manifest",
    )