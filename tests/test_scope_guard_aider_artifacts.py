"""Regression tests for Aider runtime-artifact exclusion in scope_guard.

Every test is self-contained and does not touch the filesystem or Git.
"""

import os
import textwrap
from unittest import mock

import pytest

from atlas_dev_controller.scope_guard import (
    AIDER_RUNTIME_ARTIFACTS,
    AIDER_RUNTIME_DIRECTORY_PREFIXES,
    ScopeViolationError,
    detect_changed_files,
    is_aider_runtime_artifact,
    normalize_path,
    validate_file_scope,
    validate_post_aider_scope,
)


# ── is_aider_runtime_artifact ────────────────────────────────────────────


class TestIsAiderRuntimeArtifact:
    """Positive and negative identification of Aider artifacts."""

    @pytest.mark.parametrize(
        "path",
        [
            ".aider.chat.history.md",
            ".aider.input.history",
            ".aider.tags.cache.v4/some_file.tags",
            ".aider.tags.cache.v4/subdir/deep.tags",
            # Windows-style separators
            ".aider.tags.cache.v4\\some_file.tags",
        ],
    )
    def test_known_artifacts_are_recognised(self, path):
        assert is_aider_runtime_artifact(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "README.md",
            ".gitignore",
            "aider.chat.history.md",  # missing leading dot
            ".aider.chat.history.md.bak",  # suffix added
            ".aider.tags.cache.v3/old.tags",  # wrong version
            "some/.aider.unexpected/file.py",
            "",
        ],
    )
    def test_non_artifacts_are_rejected(self, path):
        assert is_aider_runtime_artifact(path) is False

    def test_tags_cache_directory_root_itself(self):
        assert is_aider_runtime_artifact(".aider.tags.cache.v4") is True

    def test_nested_history_file(self):
        """History file appearing inside a subdirectory is still an artifact."""
        assert is_aider_runtime_artifact("subdir/.aider.chat.history.md") is True


# ── validate_post_aider_scope — artifact filtering ──────────────────────


def _fake_detect(paths):
    """Return a factory that patches detect_changed_files."""
    return mock.patch(
        "atlas_dev_controller.scope_guard.detect_changed_files",
        return_value=list(paths),
    )


class TestValidatePostAiderScopeArtifacts:
    """Artifacts must be silently excluded; production files still enforced."""

    def test_only_artifacts_returns_empty(self):
        artifacts = [
            ".aider.chat.history.md",
            ".aider.input.history",
            ".aider.tags.cache.v4/foo.tags",
        ]
        with _fake_detect(artifacts):
            result = validate_post_aider_scope(allowed_files=[])
        assert result == []

    def test_artifacts_plus_allowed_production_file(self):
        changed = [
            ".aider.chat.history.md",
            "src/main.py",
        ]
        with _fake_detect(changed):
            result = validate_post_aider_scope(allowed_files=["src/main.py"])
        assert result == ["src/main.py"]

    def test_artifacts_plus_disallowed_production_file_raises(self):
        changed = [
            ".aider.input.history",
            "src/sneaky.py",
        ]
        with _fake_detect(changed):
            with pytest.raises(ScopeViolationError, match="sneaky.py"):
                validate_post_aider_scope(allowed_files=["src/main.py"])

    def test_no_changes_returns_empty(self):
        with _fake_detect([]):
            result = validate_post_aider_scope(allowed_files=["anything.py"])
        assert result == []

    def test_production_violation_still_fails_closed(self):
        """Arbitrary unknown file must still raise even when artifacts present."""
        changed = [
            ".aider.tags.cache.v4/x.tags",
            "planning/secret.py",
        ]
        with _fake_detect(changed):
            with pytest.raises(ScopeViolationError, match="secret.py"):
                validate_post_aider_scope(allowed_files=["src/ok.py"])


# ── validate_file_scope is NOT affected ──────────────────────────────────


class TestValidateFileScopeUnchanged:
    """Pre-Aider file-scope validation must NOT exclude artifacts.

    Artifacts are only excluded from *post-Aider* working-tree detection.
    If someone explicitly passes an artifact path to validate_file_scope it
    must still be checked against the allowed list.
    """

    def test_artifact_path_not_in_allowed_raises(self):
        with pytest.raises(ScopeViolationError):
            validate_file_scope(
                [".aider.chat.history.md"],
                allowed_files=["src/main.py"],
            )

    def test_artifact_path_in_allowed_passes(self):
        validate_file_scope(
            [".aider.chat.history.md"],
            allowed_files=[".aider.chat.history.md"],
        )


# ── Constants sanity ─────────────────────────────────────────────────────


class TestConstantsSanity:
    def test_artifacts_frozenset(self):
        assert isinstance(AIDER_RUNTIME_ARTIFACTS, frozenset)
        assert ".aider.chat.history.md" in AIDER_RUNTIME_ARTIFACTS
        assert ".aider.input.history" in AIDER_RUNTIME_ARTIFACTS

    def test_directory_prefixes_frozenset(self):
        assert isinstance(AIDER_RUNTIME_DIRECTORY_PREFIXES, frozenset)
        assert ".aider.tags.cache.v4/" in AIDER_RUNTIME_DIRECTORY_PREFIXES
