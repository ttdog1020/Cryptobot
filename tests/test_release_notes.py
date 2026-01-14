"""
Unit tests for scripts/release_notes.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from release_notes import ReleaseNotesGenerator


class TestReleaseNotesGenerator:
    """Test suite for ReleaseNotesGenerator class"""

    @pytest.fixture
    def generator(self):
        """Create a ReleaseNotesGenerator instance for testing"""
        return ReleaseNotesGenerator()

    def test_extract_pr_number_from_merge_commit(self, generator):
        """Test extracting PR number from GitHub merge commit message"""
        message = "Merge pull request from user/feat-branch (PR #42)"
        assert generator.extract_pr_number(message) == 42

    def test_extract_pr_number_from_squash_commit(self, generator):
        """Test extracting PR number from squash merge message"""
        message = "Add trailing stop loss feature (#45)"
        assert generator.extract_pr_number(message) == 45

    def test_extract_pr_number_no_pr(self, generator):
        """Test commit message without PR number returns None"""
        message = "Direct commit without PR"
        assert generator.extract_pr_number(message) is None

    def test_extract_pr_number_multiple_matches(self, generator):
        """Test that first PR number is returned when multiple exist"""
        message = "Fix (#123) and close (#456)"
        assert generator.extract_pr_number(message) == 123

    def test_categorize_enhancement_label(self, generator):
        """Test categorization with enhancement label"""
        commit = {"message": "feat: add something"}
        pr_metadata = {
            "title": "Add new feature",
            "labels": [{"name": "enhancement"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Added"

    def test_categorize_bug_label(self, generator):
        """Test categorization with bug label"""
        commit = {"message": "fix: resolve issue"}
        pr_metadata = {
            "title": "Fix crash",
            "labels": [{"name": "bug"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Fixed"

    def test_categorize_security_label(self, generator):
        """Test categorization with security label"""
        commit = {"message": "security: patch CVE"}
        pr_metadata = {
            "title": "Patch vulnerability",
            "labels": [{"name": "security"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Security"

    def test_categorize_refactor_label(self, generator):
        """Test categorization with refactor label"""
        commit = {"message": "refactor: clean code"}
        pr_metadata = {
            "title": "Refactor module",
            "labels": [{"name": "refactor"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Changed"

    def test_categorize_docs_label(self, generator):
        """Test categorization with docs label"""
        commit = {"message": "docs: update readme"}
        pr_metadata = {
            "title": "Update README",
            "labels": [{"name": "documentation"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Changed"

    def test_categorize_feature_label_alias(self, generator):
        """Test that 'feature' label works as alias for 'enhancement'"""
        commit = {"message": "add feature"}
        pr_metadata = {
            "title": "Add feature",
            "labels": [{"name": "feature"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Added"

    def test_categorize_fix_label_alias(self, generator):
        """Test that 'fix' label works as alias for 'bug'"""
        commit = {"message": "fix issue"}
        pr_metadata = {
            "title": "Fix issue",
            "labels": [{"name": "fix"}],
            "state": "merged"
        }
        category = generator.categorize_change(commit, pr_metadata)
        assert category == "Fixed"

    def test_categorize_fallback_to_commit_message_add(self, generator):
        """Test fallback to commit message for 'add' keyword"""
        commit = {"message": "add new functionality"}
        category = generator.categorize_change(commit, None)
        assert category == "Added"

    def test_categorize_fallback_to_commit_message_fix(self, generator):
        """Test fallback to commit message for 'fix' keyword"""
        commit = {"message": "fix broken test"}
        category = generator.categorize_change(commit, None)
        assert category == "Fixed"

    def test_categorize_fallback_to_commit_message_security(self, generator):
        """Test fallback to commit message for 'security' keyword"""
        commit = {"message": "security patch for CVE-2025-1234"}
        category = generator.categorize_change(commit, None)
        assert category == "Security"

    def test_categorize_default_changed(self, generator):
        """Test default categorization is 'Changed'"""
        commit = {"message": "random commit message"}
        category = generator.categorize_change(commit, None)
        assert category == "Changed"

    @patch('subprocess.run')
    def test_get_commits_since_tag(self, mock_run, generator):
        """Test retrieving commits since last tag"""
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="abc123|Add feature (#42)|author|2025-01-01 10:00:00 -0700\ndef456|Fix bug (#43)|author|2025-01-02 10:00:00 -0700\n"
        )
        
        commits = generator.get_commits_since(since="v1.0.0")
        
        assert len(commits) == 2
        assert commits[0]['hash'] == 'abc123'
        assert commits[0]['message'] == 'Add feature (#42)'
        assert commits[1]['hash'] == 'def456'
        assert commits[1]['message'] == 'Fix bug (#43)'

    @patch('subprocess.run')
    def test_get_commits_since_date(self, mock_run, generator):
        """Test retrieving commits since specific date"""
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="abc123|Add feature|author|2025-01-01 10:00:00 -0700\n"
        )
        
        commits = generator.get_commits_since(since="2025-01-01")
        
        assert len(commits) == 1
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert '--since=2025-01-01' in call_args

    @patch('subprocess.run')
    def test_get_commits_no_tags(self, mock_run, generator):
        """Test retrieving commits when no date provided"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123|Initial commit|author|2025-01-01 10:00:00 -0700\n"
        )
        
        commits = generator.get_commits_since()
        
        assert len(commits) == 1

    @patch('subprocess.run')
    def test_get_pr_metadata_success(self, mock_run, generator):
        """Test fetching PR metadata via GitHub CLI"""
        pr_data = {
            "title": "Add feature",
            "labels": [{"name": "enhancement"}],
            "state": "merged",
            "mergedAt": "2025-01-01T10:00:00Z"
        }
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(pr_data)
        )
        
        metadata = generator.get_pr_metadata(42)
        
        assert metadata['title'] == "Add feature"
        assert len(metadata['labels']) == 1
        assert metadata['labels'][0]['name'] == "enhancement"

    @patch('subprocess.run')
    def test_get_pr_metadata_not_found(self, mock_run, generator):
        """Test fetching PR metadata when PR doesn't exist"""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        
        metadata = generator.get_pr_metadata(999)
        
        assert metadata is None

    @patch('subprocess.run')
    def test_get_pr_metadata_invalid_json(self, mock_run, generator):
        """Test handling invalid JSON from gh CLI"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid json"
        )
        
        metadata = generator.get_pr_metadata(42)
        
        assert metadata is None

    def test_integration_determinism(self, generator):
        """Test that running generator twice produces same output"""
        commit = {"message": "Add feature (#42)"}
        pr_metadata = {
            "title": "Add feature",
            "labels": [{"name": "enhancement"}],
            "state": "merged"
        }
        
        result1 = generator.categorize_change(commit, pr_metadata)
        result2 = generator.categorize_change(commit, pr_metadata)
        
        assert result1 == result2

    def test_category_map_completeness(self, generator):
        """Ensure CATEGORY_MAP covers all expected labels"""
        expected_labels = [
            'enhancement', 'feature', 'bug', 'fix', 
            'security', 'refactor', 'chore', 'docs', 'documentation'
        ]
        
        for label in expected_labels:
            commit = {"message": "test"}
            pr_metadata = {"labels": [{"name": label}], "state": "merged", "title": "Test"}
            category = generator.categorize_change(commit, pr_metadata)
            assert category in ["Added", "Fixed", "Security", "Changed"]


# Edge cases and error handling

def test_empty_commit_log():
    """Test handling empty commit log"""
    gen = ReleaseNotesGenerator()
    with patch('subprocess.run', return_value=MagicMock(returncode=0, stdout="")):
        commits = gen.get_commits_since()
        assert commits == []


def test_malformed_commit_message():
    """Test handling commit message without delimiter"""
    gen = ReleaseNotesGenerator()
    with patch('subprocess.run', return_value=MagicMock(returncode=0, stdout="abc123")):
        commits = gen.get_commits_since()
        # Should handle gracefully or skip malformed commits
        assert len(commits) == 0


def test_pr_number_boundary_values():
    """Test PR number extraction with edge cases"""
    gen = ReleaseNotesGenerator()
    
    # Minimum valid PR number
    assert gen.extract_pr_number("Fix (#1)") == 1
    
    # Large PR number
    assert gen.extract_pr_number("Update (#99999)") == 99999
    
    # Invalid: negative number (regex won't match)
    assert gen.extract_pr_number("Invalid (#-1)") is None
    
    # Zero
    assert gen.extract_pr_number("Invalid (#0)") == 0  # Technically extracts it


def test_unicode_in_commit_messages():
    """Test handling unicode characters in PR titles"""
    gen = ReleaseNotesGenerator()
    commit = {"message": "feat: emoji 🚀"}
    pr_metadata = {
        "title": "Add emoji support 🎉 (#42)",
        "labels": [{"name": "enhancement"}],
        "state": "merged"
    }
    category = gen.categorize_change(commit, pr_metadata)
    assert category == "Added"
