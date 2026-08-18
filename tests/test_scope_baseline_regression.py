"""Regression tests for Atlas Development Controller scope baseline handling.

These tests focus on the specific issue where pre-existing file modifications
were incorrectly reported as Aider scope violations. The controller must
distinguish between changes that existed before Aider ran versus new changes
introduced during the Aider run.
"""

import os
import tempfile
import unittest
from pathlib import Path
from typing import FrozenSet, List
from unittest.mock import Mock, patch

from atlas_dev_controller.scope_guard import (
    ScopeViolationError,
    capture_baseline_changes,
    normalize_path,
    validate_post_aider_scope,
)


class TestScopeBaselineRegression(unittest.TestCase):
    """Test scope validation with pre-existing changes baseline."""

    def setUp(self):
        """Set up a temporary git repository for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: self._cleanup_test_dir())
        
    def _cleanup_test_dir(self):
        """Clean up the temporary test directory."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_pre_existing_change_not_reported_as_violation(self):
        """A file already modified before Aider must not be reported as violation."""
        allowed_files = ["allowed_file.py"]
        
        # Simulate baseline: tasks/unreal_production_roundtrip.json was already modified
        baseline_changes: FrozenSet[str] = frozenset([
            normalize_path("tasks/unreal_production_roundtrip.json")
        ])
        
        # Mock git commands to return the same file still modified after Aider
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = ["tasks/unreal_production_roundtrip.json"]
            
            # This should NOT raise ScopeViolationError because the file was in baseline
            try:
                result = validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
                # Should return the changed file for logging but not fail
                self.assertEqual(result, ["tasks/unreal_production_roundtrip.json"])
            except ScopeViolationError:
                self.fail("Pre-existing change incorrectly reported as Aider scope violation")

    def test_new_change_outside_scope_fails_closed(self):
        """A newly modified file outside allowed_files must fail closed."""
        allowed_files = ["allowed_file.py"]
        
        # Empty baseline - no pre-existing changes
        baseline_changes: FrozenSet[str] = frozenset()
        
        # Mock git commands to return a new unauthorized change
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = ["unauthorized_file.py"]
            
            # This SHOULD raise ScopeViolationError because it's a new change outside scope
            with self.assertRaises(ScopeViolationError) as cm:
                validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
            
            self.assertIn("unauthorized_file.py", str(cm.exception))
            self.assertIn("outside the approved scope", str(cm.exception))

    def test_new_change_inside_scope_passes(self):
        """A newly modified file inside allowed_files must pass validation."""
        allowed_files = ["allowed_file.py"]
        
        # Empty baseline - no pre-existing changes
        baseline_changes: FrozenSet[str] = frozenset()
        
        # Mock git commands to return a new authorized change
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = ["allowed_file.py"]
            
            # This should NOT raise ScopeViolationError
            try:
                result = validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
                self.assertEqual(result, ["allowed_file.py"])
            except ScopeViolationError:
                self.fail("Authorized new change incorrectly failed validation")

    def test_mixed_baseline_and_new_changes(self):
        """Test combination of baseline changes and new changes."""
        allowed_files = ["allowed_file.py", "another_allowed.py"]
        
        # Baseline contains one pre-existing change outside scope
        baseline_changes: FrozenSet[str] = frozenset([
            normalize_path("tasks/unreal_production_roundtrip.json")
        ])
        
        # Mock git to return baseline change + new authorized change + new unauthorized change
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = [
                "tasks/unreal_production_roundtrip.json",  # pre-existing (should be ignored)
                "allowed_file.py",                         # new authorized (should pass)
                "unauthorized_new.py"                      # new unauthorized (should fail)
            ]
            
            # Should fail on the new unauthorized change, ignoring the baseline change
            with self.assertRaises(ScopeViolationError) as cm:
                validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
            
            self.assertIn("unauthorized_new.py", str(cm.exception))
            # Should NOT mention the baseline file
            self.assertNotIn("unreal_production_roundtrip.json", str(cm.exception))

    def test_capture_baseline_changes(self):
        """Test baseline capture functionality."""
        # Mock git commands to return some changed files
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = [
                "tasks/unreal_production_roundtrip.json",
                "some/other/file.py"
            ]
            
            baseline = capture_baseline_changes(self.test_dir)
            
            # Should return normalized paths as frozenset
            expected = frozenset([
                normalize_path("tasks/unreal_production_roundtrip.json"),
                normalize_path("some/other/file.py")
            ])
            self.assertEqual(baseline, expected)

    def test_aider_runtime_artifacts_still_excluded(self):
        """Aider runtime artifacts should still be excluded from scope validation."""
        allowed_files = ["allowed_file.py"]
        baseline_changes: FrozenSet[str] = frozenset()
        
        # Mock git to return Aider artifacts + unauthorized change
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = [
                ".aider.chat.history.md",      # Aider artifact (should be ignored)
                ".aider.input.history",        # Aider artifact (should be ignored)
                "unauthorized_file.py"         # Unauthorized change (should fail)
            ]
            
            # Should fail only on unauthorized_file.py, ignoring Aider artifacts
            with self.assertRaises(ScopeViolationError) as cm:
                validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
            
            self.assertIn("unauthorized_file.py", str(cm.exception))
            self.assertNotIn(".aider", str(cm.exception))

    def test_empty_baseline_empty_changes(self):
        """Test edge case: no baseline changes, no new changes."""
        allowed_files = ["allowed_file.py"]
        baseline_changes: FrozenSet[str] = frozenset()
        
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = []
            
            result = validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
            self.assertEqual(result, [])

    def test_all_changes_in_baseline(self):
        """Test case where all current changes were in baseline (no new changes)."""
        allowed_files = ["allowed_file.py"]
        
        # All current changes were in baseline
        baseline_changes: FrozenSet[str] = frozenset([
            normalize_path("tasks/unreal_production_roundtrip.json"),
            normalize_path("some/other/modified.py")
        ])
        
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            # Same files still changed, but they were all in baseline
            mock_detect.return_value = [
                "tasks/unreal_production_roundtrip.json",
                "some/other/modified.py"
            ]
            
            # Should not raise any errors since no NEW changes
            result = validate_post_aider_scope(allowed_files, baseline_changes, self.test_dir)
            self.assertEqual(len(result), 2)  # Both files returned for logging

    def test_backward_compatibility_no_baseline_parameter(self):
        """Test backward compatibility: omitted baseline_changes should work like empty baseline."""
        allowed_files = ["allowed_file.py"]
        
        # Mock git to return unauthorized change
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = ["unauthorized_file.py"]
            
            # Call without baseline_changes parameter (backward compatibility)
            with self.assertRaises(ScopeViolationError) as cm:
                validate_post_aider_scope(allowed_files, repo_dir=self.test_dir)
            
            self.assertIn("unauthorized_file.py", str(cm.exception))
            self.assertIn("outside the approved scope", str(cm.exception))

    def test_backward_compatibility_none_baseline_parameter(self):
        """Test backward compatibility: explicit None baseline_changes should work like empty baseline."""
        allowed_files = ["allowed_file.py"]
        
        # Mock git to return authorized change
        with patch('atlas_dev_controller.scope_guard.detect_changed_files') as mock_detect:
            mock_detect.return_value = ["allowed_file.py"]
            
            # Call with explicit None baseline_changes (backward compatibility)
            try:
                result = validate_post_aider_scope(allowed_files, None, self.test_dir)
                self.assertEqual(result, ["allowed_file.py"])
            except ScopeViolationError:
                self.fail("Authorized change with None baseline incorrectly failed validation")


if __name__ == '__main__':
    unittest.main()
