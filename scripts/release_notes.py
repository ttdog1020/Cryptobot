#!/usr/bin/env python3
"""
Automatic CHANGELOG.md Maintenance Script

Fetches merged PRs from GitHub and updates CHANGELOG.md with categorized entries.
Supports tech-debt PR detection and idempotent updates.

Usage:
    python scripts/release_notes.py [--dry-run] [--since COMMIT_SHA]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Label-to-section mapping (Keep a Changelog categories)
LABEL_SECTION_MAP = {
    'feature': 'Added',
    'enhancement': 'Added',
    'bugfix': 'Fixed',
    'bug': 'Fixed',
    'fix': 'Fixed',
    'breaking-change': 'Changed',
    'refactor': 'Changed',
    'tech-debt': 'Maintenance',
    'chore': 'Maintenance',
    'cleanup': 'Maintenance',
    'maintenance': 'Maintenance',
    'documentation': 'Maintenance',
    'removal': 'Removed',
    'deprecation': 'Removed',
}

# Labels that skip changelog entry
SKIP_LABELS = {'no-changelog', 'skip-changelog'}

# Standard sections in Keep a Changelog format
CHANGELOG_SECTIONS = ['Added', 'Changed', 'Fixed', 'Removed', 'Maintenance']


def run_command(cmd: List[str], check: bool = True) -> Tuple[int, str, str]:
    """Run shell command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_merged_prs_since(since_ref: Optional[str] = None) -> List[Dict]:
    """
    Fetch merged PRs from GitHub using gh CLI.
    
    Args:
        since_ref: Commit SHA or tag to fetch PRs since. If None, uses last tag.
    
    Returns:
        List of PR dictionaries with keys: number, title, labels, mergedAt
    """
    # Determine the "since" reference
    if not since_ref:
        # Find last tag
        _, last_tag, _ = run_command(['git', 'describe', '--tags', '--abbrev=0'], check=False)
        if not last_tag:
            # No tags - use initial commit
            _, since_ref, _ = run_command(['git', 'rev-list', '--max-parents=0', 'HEAD'])
        else:
            since_ref = last_tag
    
    print(f"Fetching PRs merged since: {since_ref}")
    
    # Get commits since reference
    _, commit_range, _ = run_command(['git', 'rev-list', f'{since_ref}..HEAD'])
    commit_shas = commit_range.split('\n') if commit_range else []
    
    if not commit_shas:
        print("No new commits since last reference")
        return []
    
    # Fetch all merged PRs to staging
    _, pr_json, _ = run_command([
        'gh', 'pr', 'list',
        '--state', 'merged',
        '--base', 'staging',
        '--limit', '100',
        '--json', 'number,title,labels,mergedAt,mergeCommit'
    ])
    
    if not pr_json:
        return []
    
    all_prs = json.loads(pr_json)
    
    # Filter PRs that were merged in our commit range
    commit_set = set(commit_shas)
    merged_prs = []
    
    for pr in all_prs:
        merge_commit = pr.get('mergeCommit', {}).get('oid', '')
        if merge_commit and merge_commit[:7] in [sha[:7] for sha in commit_shas]:
            merged_prs.append({
                'number': pr['number'],
                'title': pr['title'],
                'labels': [label['name'] for label in pr.get('labels', [])],
                'mergedAt': pr.get('mergedAt', ''),
            })
    
    return merged_prs


def categorize_pr(pr: Dict) -> Optional[str]:
    """
    Determine which changelog section a PR belongs to.
    
    Args:
        pr: PR dictionary with 'labels' key
    
    Returns:
        Section name or None if PR should be skipped
    """
    labels = set(pr['labels'])
    
    # Check skip labels
    if labels & SKIP_LABELS:
        return None
    
    # Find first matching label
    for label in labels:
        section = LABEL_SECTION_MAP.get(label.lower())
        if section:
            return section
    
    # Default to Changed if no matching label
    return 'Changed'


def parse_changelog(changelog_path: Path) -> Dict[str, List[str]]:
    """
    Parse CHANGELOG.md and extract [Unreleased] section entries.
    
    Returns:
        Dict mapping section name to list of existing entries
    """
    if not changelog_path.exists():
        return {section: [] for section in CHANGELOG_SECTIONS}
    
    content = changelog_path.read_text(encoding='utf-8')
    sections = {section: [] for section in CHANGELOG_SECTIONS}
    
    # Find [Unreleased] section
    unreleased_match = re.search(
        r'## \[Unreleased\](.*?)(?=\n## |\Z)',
        content,
        re.DOTALL
    )
    
    if not unreleased_match:
        return sections
    
    unreleased_content = unreleased_match.group(1)
    
    # Extract each subsection
    for section in CHANGELOG_SECTIONS:
        section_match = re.search(
            rf'### {section}\n(.*?)(?=\n### |\Z)',
            unreleased_content,
            re.DOTALL
        )
        if section_match:
            entries = section_match.group(1).strip().split('\n')
            sections[section] = [e.strip() for e in entries if e.strip() and e.strip().startswith('-')]
    
    return sections


def format_pr_entry(pr: Dict) -> str:
    """Format PR as changelog entry: '- <title> (#<number>)'"""
    return f"- {pr['title']} (#{pr['number']})"


def update_changelog(
    changelog_path: Path,
    new_entries: Dict[str, List[str]],
    dry_run: bool = False
) -> bool:
    """
    Update CHANGELOG.md with new entries (idempotent).
    
    Args:
        changelog_path: Path to CHANGELOG.md
        new_entries: Dict mapping section to list of new entry strings
        dry_run: If True, print changes without writing
    
    Returns:
        True if changes were made, False otherwise
    """
    # Parse existing entries
    existing = parse_changelog(changelog_path)
    
    # Merge new entries (avoiding duplicates)
    updated_sections = {}
    changes_made = False
    
    for section in CHANGELOG_SECTIONS:
        existing_set = set(existing.get(section, []))
        new_set = set(new_entries.get(section, []))
        
        # Add only new entries
        to_add = new_set - existing_set
        if to_add:
            changes_made = True
            updated_sections[section] = sorted(existing_set | new_set)
        else:
            updated_sections[section] = sorted(existing_set)
    
    if not changes_made:
        print("No new entries to add (idempotent)")
        return False
    
    # Rebuild [Unreleased] section
    unreleased_lines = ['## [Unreleased]', '']
    for section in CHANGELOG_SECTIONS:
        unreleased_lines.append(f'### {section}')
        unreleased_lines.append('')
        for entry in updated_sections[section]:
            unreleased_lines.append(entry)
        unreleased_lines.append('')
    
    unreleased_block = '\n'.join(unreleased_lines)
    
    # Read full changelog
    if changelog_path.exists():
        content = changelog_path.read_text(encoding='utf-8')
        
        # Replace [Unreleased] section
        new_content = re.sub(
            r'## \[Unreleased\].*?(?=\n## |\Z)',
            unreleased_block,
            content,
            flags=re.DOTALL
        )
    else:
        # Create new changelog
        header = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""
        new_content = header + unreleased_block
    
    if dry_run:
        print("\n=== DRY RUN: Would update CHANGELOG.md ===")
        print(new_content)
        print("==========================================\n")
    else:
        changelog_path.write_text(new_content, encoding='utf-8')
        print(f"✓ Updated {changelog_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Update CHANGELOG.md with merged PRs')
    parser.add_argument('--dry-run', action='store_true', help='Print changes without writing')
    parser.add_argument('--since', help='Commit SHA or tag to fetch PRs since')
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    changelog_path = repo_root / 'CHANGELOG.md'
    
    print("Fetching merged PRs from GitHub...")
    merged_prs = get_merged_prs_since(args.since)
    
    if not merged_prs:
        print("No PRs found")
        return 0
    
    print(f"Found {len(merged_prs)} merged PR(s)")
    
    # Categorize PRs
    new_entries = {section: [] for section in CHANGELOG_SECTIONS}
    skipped = []
    
    for pr in merged_prs:
        section = categorize_pr(pr)
        if section:
            entry = format_pr_entry(pr)
            new_entries[section].append(entry)
            print(f"  [{section}] PR #{pr['number']}: {pr['title']}")
        else:
            skipped.append(pr)
            print(f"  [SKIP] PR #{pr['number']}: {pr['title']} (has skip label)")
    
    # Update changelog
    if update_changelog(changelog_path, new_entries, dry_run=args.dry_run):
        if not args.dry_run:
            print(f"\n✓ CHANGELOG.md updated with {sum(len(v) for v in new_entries.values())} entries")
        return 0
    else:
        print("\nNo changes needed")
        return 0


if __name__ == '__main__':
    sys.exit(main())
