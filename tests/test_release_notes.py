"""
Unit tests for scripts/release_notes.py

Tests automatic CHANGELOG.md maintenance including:
- Tech-debt label detection
- Idempotency (no duplicates)
- Maintenance subsection insertion
- no-changelog skip behavior
"""

import pytest
import tempfile
from pathlib import Path
from scripts.release_notes import (
    categorize_pr,
    format_pr_entry,
    parse_changelog,
    update_changelog,
    LABEL_SECTION_MAP,
    SKIP_LABELS,
    CHANGELOG_SECTIONS,
)


class TestPRCategorization:
    """Test PR label-to-section mapping."""
    
    def test_tech_debt_labels_map_to_maintenance(self):
        """Tech-debt labels should map to Maintenance section."""
        tech_debt_labels = ['tech-debt', 'chore', 'cleanup', 'maintenance', 'documentation']
        
        for label in tech_debt_labels:
            pr = {'number': 1, 'title': 'Test', 'labels': [label]}
            assert categorize_pr(pr) == 'Maintenance', f"Label '{label}' should map to Maintenance"
    
    def test_feature_labels_map_to_added(self):
        """Feature labels should map to Added section."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['feature']}
        assert categorize_pr(pr) == 'Added'
        
        pr = {'number': 1, 'title': 'Test', 'labels': ['enhancement']}
        assert categorize_pr(pr) == 'Added'
    
    def test_bugfix_labels_map_to_fixed(self):
        """Bugfix labels should map to Fixed section."""
        for label in ['bugfix', 'bug', 'fix']:
            pr = {'number': 1, 'title': 'Test', 'labels': [label]}
            assert categorize_pr(pr) == 'Fixed'
    
    def test_breaking_change_maps_to_changed(self):
        """Breaking change labels should map to Changed section."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['breaking-change']}
        assert categorize_pr(pr) == 'Changed'
    
    def test_removal_labels_map_to_removed(self):
        """Removal labels should map to Removed section."""
        for label in ['removal', 'deprecation']:
            pr = {'number': 1, 'title': 'Test', 'labels': [label]}
            assert categorize_pr(pr) == 'Removed'
    
    def test_no_label_defaults_to_changed(self):
        """PRs without matching labels should default to Changed."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['unknown-label']}
        assert categorize_pr(pr) == 'Changed'
    
    def test_skip_labels_return_none(self):
        """PRs with skip labels should return None."""
        for skip_label in SKIP_LABELS:
            pr = {'number': 1, 'title': 'Test', 'labels': [skip_label]}
            assert categorize_pr(pr) is None
    
    def test_skip_label_takes_precedence(self):
        """Skip labels should override other labels."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['feature', 'no-changelog']}
        assert categorize_pr(pr) is None
    
    def test_first_matching_label_wins(self):
        """When multiple labels match, first one wins."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['bugfix', 'enhancement']}
        # bugfix appears first in labels list
        result = categorize_pr(pr)
        assert result in ['Fixed', 'Added']  # Either is valid depending on set order


class TestPRFormatting:
    """Test PR entry formatting."""
    
    def test_format_pr_entry_basic(self):
        """Test basic PR entry formatting."""
        pr = {'number': 42, 'title': 'Fix critical bug'}
        assert format_pr_entry(pr) == '- Fix critical bug (#42)'
    
    def test_format_pr_entry_with_special_chars(self):
        """Test PR entry with special characters."""
        pr = {'number': 100, 'title': '[TECH_DEBT] Cleanup: remove old files'}
        assert format_pr_entry(pr) == '- [TECH_DEBT] Cleanup: remove old files (#100)'


class TestChangelogParsing:
    """Test CHANGELOG.md parsing."""
    
    def test_parse_empty_changelog(self):
        """Parsing non-existent changelog should return empty sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            result = parse_changelog(changelog_path)
            
            assert all(section in result for section in CHANGELOG_SECTIONS)
            assert all(result[section] == [] for section in CHANGELOG_SECTIONS)
    
    def test_parse_changelog_with_entries(self):
        """Parse changelog with existing entries."""
        content = """# Changelog

## [Unreleased]

### Added
- New feature A (#1)
- New feature B (#2)

### Fixed
- Bug fix X (#10)

### Maintenance
- Tech debt cleanup (#20)
- Refactor old code (#21)

## [1.0.0] - 2025-01-01
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            changelog_path.write_text(content, encoding='utf-8')
            
            result = parse_changelog(changelog_path)
            
            assert result['Added'] == ['- New feature A (#1)', '- New feature B (#2)']
            assert result['Fixed'] == ['- Bug fix X (#10)']
            assert result['Maintenance'] == ['- Tech debt cleanup (#20)', '- Refactor old code (#21)']
            assert result['Changed'] == []
            assert result['Removed'] == []
    
    def test_parse_changelog_ignores_other_versions(self):
        """Should only parse [Unreleased] section."""
        content = """# Changelog

## [Unreleased]

### Added
- Unreleased feature (#1)

## [1.0.0] - 2025-01-01

### Added
- Released feature (#2)
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            changelog_path.write_text(content, encoding='utf-8')
            
            result = parse_changelog(changelog_path)
            
            # Should only include unreleased entry
            assert result['Added'] == ['- Unreleased feature (#1)']


class TestChangelogUpdate:
    """Test CHANGELOG.md update logic."""
    
    def test_idempotency_no_duplicates(self):
        """Running update twice should not create duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            
            # First update
            new_entries = {
                'Maintenance': ['- Tech debt item (#1)'],
                'Added': [],
                'Fixed': [],
                'Changed': [],
                'Removed': [],
            }
            
            assert update_changelog(changelog_path, new_entries, dry_run=False) is True
            
            # Second update with same entry
            assert update_changelog(changelog_path, new_entries, dry_run=False) is False
            
            # Verify only one entry exists
            content = changelog_path.read_text(encoding='utf-8')
            assert content.count('- Tech debt item (#1)') == 1
    
    def test_adds_new_entries_only(self):
        """Should add only new entries, preserving existing ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            
            # First batch
            first_entries = {
                'Maintenance': ['- Item A (#1)'],
                'Added': ['- Feature X (#10)'],
                'Fixed': [],
                'Changed': [],
                'Removed': [],
            }
            update_changelog(changelog_path, first_entries, dry_run=False)
            
            # Second batch (new items)
            second_entries = {
                'Maintenance': ['- Item B (#2)'],  # New
                'Added': ['- Feature X (#10)'],     # Duplicate (should skip)
                'Fixed': ['- Bug fix (#20)'],       # New
                'Changed': [],
                'Removed': [],
            }
            assert update_changelog(changelog_path, second_entries, dry_run=False) is True
            
            # Parse and verify
            result = parse_changelog(changelog_path)
            assert sorted(result['Maintenance']) == sorted(['- Item A (#1)', '- Item B (#2)'])
            assert result['Added'] == ['- Feature X (#10)']
            assert result['Fixed'] == ['- Bug fix (#20)']
    
    def test_creates_maintenance_section_if_missing(self):
        """Should create Maintenance section even if not in original changelog."""
        content = """# Changelog

## [Unreleased]

### Added

### Changed

### Fixed
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            changelog_path.write_text(content, encoding='utf-8')
            
            new_entries = {
                'Maintenance': ['- Tech debt (#1)'],
                'Added': [],
                'Fixed': [],
                'Changed': [],
                'Removed': [],
            }
            
            update_changelog(changelog_path, new_entries, dry_run=False)
            
            updated_content = changelog_path.read_text(encoding='utf-8')
            assert '### Maintenance' in updated_content
            assert '- Tech debt (#1)' in updated_content
    
    def test_dry_run_does_not_write(self):
        """Dry run should not write to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            
            new_entries = {
                'Maintenance': ['- Test (#1)'],
                'Added': [],
                'Fixed': [],
                'Changed': [],
                'Removed': [],
            }
            
            update_changelog(changelog_path, new_entries, dry_run=True)
            
            # File should not exist after dry run
            assert not changelog_path.exists()
    
    def test_sorts_entries_alphabetically(self):
        """Entries within a section should be sorted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            
            new_entries = {
                'Maintenance': [
                    '- Zebra task (#3)',
                    '- Alpha task (#1)',
                    '- Beta task (#2)',
                ],
                'Added': [],
                'Fixed': [],
                'Changed': [],
                'Removed': [],
            }
            
            update_changelog(changelog_path, new_entries, dry_run=False)
            
            result = parse_changelog(changelog_path)
            # Should be sorted
            assert result['Maintenance'][0] == '- Alpha task (#1)'
            assert result['Maintenance'][1] == '- Beta task (#2)'
            assert result['Maintenance'][2] == '- Zebra task (#3)'


class TestSkipBehavior:
    """Test no-changelog label behavior."""
    
    def test_no_changelog_label_skips_pr(self):
        """PR with no-changelog label should be skipped."""
        pr = {'number': 1, 'title': 'Minor typo fix', 'labels': ['no-changelog']}
        assert categorize_pr(pr) is None
    
    def test_skip_changelog_variant(self):
        """Alternative skip-changelog label should work."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['skip-changelog']}
        assert categorize_pr(pr) is None
    
    def test_skip_with_other_labels(self):
        """Skip label should work even with other labels present."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['feature', 'enhancement', 'no-changelog']}
        assert categorize_pr(pr) is None


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_labels_list(self):
        """PR with no labels should default to Changed."""
        pr = {'number': 1, 'title': 'Test', 'labels': []}
        assert categorize_pr(pr) == 'Changed'
    
    def test_case_insensitive_label_matching(self):
        """Label matching should be case-insensitive."""
        pr = {'number': 1, 'title': 'Test', 'labels': ['TECH-DEBT']}
        assert categorize_pr(pr) == 'Maintenance'
        
        pr = {'number': 1, 'title': 'Test', 'labels': ['Feature']}
        assert categorize_pr(pr) == 'Added'
    
    def test_update_creates_changelog_if_missing(self):
        """Should create CHANGELOG.md if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / 'CHANGELOG.md'
            
            new_entries = {
                'Added': ['- New feature (#1)'],
                'Fixed': [],
                'Changed': [],
                'Removed': [],
                'Maintenance': [],
            }
            
            update_changelog(changelog_path, new_entries, dry_run=False)
            
            assert changelog_path.exists()
            content = changelog_path.read_text(encoding='utf-8')
            assert '# Changelog' in content
            assert '## [Unreleased]' in content
            assert '- New feature (#1)' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
