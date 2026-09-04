import math

import pytest

from planning.production_artifact import ProductionArtifactError, ProductionArtifactManifest


def _manifest(**overrides):
    values = {
        "artifact_id": "artifact-001",
        "canonical_digital_twin_id": "soccer-twin-001",
        "representation_type": "unreal-render",
        "artifact_path": "renders/frame-0001.png",
    }
    values.update(overrides)
    return ProductionArtifactManifest(**values)


def test_manifest_digest_rejects_non_string_mapping_keys():
    manifest = _manifest(metadata={"valid": "value", 7: "ambiguous"})
    with pytest.raises(ProductionArtifactError, match="string mapping keys"):
        manifest.digest()


def test_manifest_digest_rejects_non_finite_floats():
    manifest = _manifest(metadata={"nan": math.nan})
    with pytest.raises(ProductionArtifactError, match="finite floats"):
        manifest.digest()


def test_manifest_digest_rejects_unsupported_values_instead_of_stringifying():
    manifest = _manifest(metadata={"unsupported": object()})
    with pytest.raises(ProductionArtifactError, match="unsupported value type"):
        manifest.digest()
