"""
Release Notes Generator

Generates release notes from git history and PR metadata.
Creates dated release note files and updates CHANGELOG.md.

Usage:
    python scripts/release_notes.py [--since TAG_OR_DATE] [--output DIR]
"""

import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


class ReleaseNotesGenerator:
    """Generate release notes from git history and PR metadata."""
    
    # Label to changelog category mapping
    CATEGORY_MAP = {
        'enhancement': 'Added',
        'feature': 'Added',
        'bug': 'Fixed',
        'fix': 'Fixed',
        'security': 'Security',
        'refactor': 'Changed',
        'chore': 'Changed',
        'docs': 'Changed',
        'documentation': 'Changed',
        'removed': 'Removed',
        'deprecated': 'Deprecated'
    }
    
    def __init__(self, repo_root: Path = Path('.')):
        """
        Initialize generator.
        
        Args:
            repo_root: Repository root directory
        """
        self.repo_root = Path(repo_root)
        self.release_notes_dir = self.repo_root / 'release_notes'
        self.changelog_path = self.repo_root / 'CHANGELOG.md'
        
    def get_last_release_date(self) -> Optional[str]:
        """Get date of last generated release note file."""
        if not self.release_notes_dir.exists():
            return None
        
        release_files = sorted(self.release_notes_dir.glob('*_release.md'))
        if not release_files:
            return None
        
        # Extract date from filename (YYYY-MM-DD_release.md)
        last_file = release_files[-1]
        match = re.match(r'(\d{4}-\d{2}-\d{2})_release\.md', last_file.name)
        if match:
            return match.group(1)
        
        return None
    
    def get_commits_since(self, since: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Get git commits since a reference point.
        
        Args:
            since: Tag, date, or commit hash (default: last release note date)
        
        Returns:
            List of commit dicts with hash, message, author, date
        """
        if since is None:
            since = self.get_last_release_date()
        
        if since is None:
            # Get all commits from last 30 days if no reference
            since = '30 days ago'
        
        try:
            cmd = [
                'git', 'log',
                f'--since={since}',
                '--pretty=format:%H|%s|%an|%ai',
                '--no-merges'
            ]
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('|', 3)
                if len(parts) == 4:
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1],
                        'author': parts[2],
                        'date': parts[3]
                    })
            
            return commits
        
        except subprocess.CalledProcessError:
            return []
    
    def extract_pr_number(self, commit_message: str) -> Optional[int]:
        """Extract PR number from commit message."""
        # Look for (#123) pattern
        match = re.search(r'\(#(\d+)\)', commit_message)
        if match:
            return int(match.group(1))
        
        # Look for PR #123 pattern
        match = re.search(r'PR\s+#(\d+)', commit_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None
    
    def get_pr_metadata(self, pr_number: int) -> Optional[Dict]:
        """
        Get PR metadata from GitHub CLI.
        
        Args:
            pr_number: PR number
        
        Returns:
            Dict with title, labels, state, or None if unavailable
        """
        try:
            cmd = [
                'gh', 'pr', 'view', str(pr_number),
                '--json', 'title,labels,state,mergedAt'
            ]
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            return json.loads(result.stdout)
        
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
    
    def categorize_change(self, commit: Dict, pr_metadata: Optional[Dict] = None) -> str:
        """
        Categorize a change based on commit message or PR labels.
        
        Args:
            commit: Commit dict
            pr_metadata: Optional PR metadata
        
        Returns:
            Category name (Added, Changed, Fixed, etc.)
        """
        # Try PR labels first
        if pr_metadata and 'labels' in pr_metadata:
            for label in pr_metadata['labels']:
                label_name = label.get('name', '').lower()
                category = self.CATEGORY_MAP.get(label_name)
                if category:
                    return category
        
        # Fall back to commit message analysis
        message = commit['message'].lower()
        
        if any(kw in message for kw in ['add', 'added', 'new', 'implement', 'feat']):
            return 'Added'
        elif any(kw in message for kw in ['fix', 'fixed', 'bug', 'resolve']):
            return 'Fixed'
        elif any(kw in message for kw in ['security', 'vulnerability', 'cve']):
            return 'Security'
        elif any(kw in message for kw in ['remove', 'deleted', 'drop']):
            return 'Removed'
        elif any(kw in message for kw in ['deprecate']):
            return 'Deprecated'
        else:
            return 'Changed'
    
    def format_change_entry(self, commit: Dict, pr_number: Optional[int] = None) -> str:
        """
        Format a single changelog entry.
        
        Args:
            commit: Commit dict
            pr_number: Optional PR number
        
        Returns:
            Formatted markdown line
        """
        message = commit['message'].strip()
        
        # Clean up conventional commit prefixes
        message = re.sub(r'^(feat|fix|docs|chore|refactor|test|style)(\([^)]+\))?:\s*', '', message)
        
        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:]
        
        if pr_number:
            return f"- {message} (#{pr_number})"
        else:
            return f"- {message}"
    
    def generate_release_notes(self, since: Optional[str] = None) -> Tuple[str, Dict[str, List[str]]]:
        """
        Generate release notes content.
        
        Args:
            since: Reference point for git log
        
        Returns:
            Tuple of (formatted markdown, categorized changes dict)
        """
        commits = self.get_commits_since(since)
        
        # Categorize changes
        categorized = defaultdict(list)
        
        for commit in commits:
            pr_number = self.extract_pr_number(commit['message'])
            pr_metadata = self.get_pr_metadata(pr_number) if pr_number else None
            
            category = self.categorize_change(commit, pr_metadata)
            entry = self.format_change_entry(commit, pr_number)
            
            categorized[category].append(entry)
        
        # Build markdown
        date_str = datetime.now().strftime('%Y-%m-%d')
        lines = [
            f"# Release Notes - {date_str}",
            "",
            f"**Generated:** {datetime.now().isoformat()}",
            ""
        ]
        
        # Order categories logically
        category_order = ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security']
        
        for category in category_order:
            if category in categorized:
                lines.append(f"## {category}")
                lines.append("")
                for entry in sorted(set(categorized[category])):
                    lines.append(entry)
                lines.append("")
        
        if not any(categorized.values()):
            lines.append("No changes recorded in this period.")
            lines.append("")
        
        return '\n'.join(lines), dict(categorized)
    
    def update_changelog(self, categorized: Dict[str, List[str]]) -> None:
        """
        Update CHANGELOG.md with new entries under Unreleased.
        
        Args:
            categorized: Dict of category -> list of entries
        """
        if not categorized:
            return
        
        # Read existing changelog
        if self.changelog_path.exists():
            content = self.changelog_path.read_text(encoding='utf-8')
        else:
            content = "# Changelog\n\n## [Unreleased]\n"
        
        # Find Unreleased section
        unreleased_pattern = r'## \[Unreleased\]'
        match = re.search(unreleased_pattern, content)
        
        if not match:
            # Add Unreleased section
            content = content.replace(
                '# Changelog\n',
                '# Changelog\n\n## [Unreleased]\n'
            )
            match = re.search(unreleased_pattern, content)
        
        # Build new entries
        new_entries = []
        for category in ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security']:
            if category in categorized:
                new_entries.append(f"\n### {category}")
                for entry in sorted(set(categorized[category])):
                    new_entries.append(entry)
        
        if new_entries:
            # Insert after [Unreleased]
            insert_pos = match.end()
            updated_content = (
                content[:insert_pos] +
                '\n' + '\n'.join(new_entries) + '\n' +
                content[insert_pos:]
            )
            
            self.changelog_path.write_text(updated_content, encoding='utf-8')
    
    def save_release_note(self, content: str, date: Optional[str] = None) -> Path:
        """
        Save release note to file.
        
        Args:
            content: Markdown content
            date: Date string (default: today)
        
        Returns:
            Path to saved file
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        self.release_notes_dir.mkdir(exist_ok=True)
        
        filename = f"{date}_release.md"
        filepath = self.release_notes_dir / filename
        
        filepath.write_text(content, encoding='utf-8')
        
        return filepath
    
    def run(self, since: Optional[str] = None, update_changelog: bool = True) -> Tuple[Path, Dict]:
        """
        Run full release notes generation.
        
        Args:
            since: Reference point for git log
            update_changelog: Whether to update CHANGELOG.md
        
        Returns:
            Tuple of (release note path, categorized changes)
        """
        content, categorized = self.generate_release_notes(since)
        
        filepath = self.save_release_note(content)
        
        if update_changelog:
            self.update_changelog(categorized)
        
        return filepath, categorized


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate release notes')
    parser.add_argument(
        '--since',
        help='Reference point (tag, date, or commit hash)',
        default=None
    )
    parser.add_argument(
        '--output',
        help='Output directory for release notes',
        type=Path,
        default=None
    )
    parser.add_argument(
        '--no-changelog',
        help='Do not update CHANGELOG.md',
        action='store_true'
    )
    
    args = parser.parse_args()
    
    generator = ReleaseNotesGenerator()
    
    if args.output:
        generator.release_notes_dir = args.output
    
    filepath, categorized = generator.run(
        since=args.since,
        update_changelog=not args.no_changelog
    )
    
    print(f"✓ Release notes generated: {filepath}")
    
    if not args.no_changelog and categorized:
        print(f"✓ CHANGELOG.md updated with {sum(len(v) for v in categorized.values())} entries")
    
    return 0


if __name__ == '__main__':
    exit(main())
