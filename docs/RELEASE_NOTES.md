# 📝 Release Notes System

## Overview

The CryptoBot project uses an **automated release notes system** that generates structured changelogs from git history and pull request metadata. This ensures consistent, comprehensive release documentation with minimal manual effort.

---

## Components

### 1. CHANGELOG.md
Standard [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format file at the repository root.

**Structure:**
```markdown
# Changelog

## [Unreleased]
### Added
- New features from enhancement PRs

### Changed
- Refactors, chores, documentation updates

### Fixed
- Bug fixes from bug/fix labeled PRs

### Security
- Security patches and vulnerability fixes

## [1.0.0] - 2025-01-15
...
```

### 2. scripts/release_notes.py
Python script that generates release notes automatically.

**Key Features:**
- Parses git log since last release tag
- Extracts PR numbers from commit messages
- Fetches PR metadata using GitHub CLI (labels, title, author)
- Categorizes changes based on labels
- Updates CHANGELOG.md Unreleased section

### 3. .github/workflows/release_notes.yml
GitHub Actions workflow that runs on every push to `staging`.

**Behavior:**
- Triggers automatically on staging branch updates
- Runs `scripts/release_notes.py`
- Commits updated CHANGELOG.md back to staging
- Uses `[skip ci]` to prevent infinite loops

### 4. PR Template Updates
Guides contributors to add appropriate labels for automatic categorization.

---

## Label-to-Category Mapping

| PR Labels | Release Notes Category |
|-----------|------------------------|
| `enhancement`, `feature` | **Added** |
| `bug`, `fix` | **Fixed** |
| `security` | **Security** |
| `refactor`, `chore` | **Changed** |
| `docs`, `documentation` | **Changed** |
| `breaking` | **Changed** (with ⚠️ prefix) |

**Fallback Logic:**
If no labels are present, the script analyzes commit messages:
- Keywords: "add", "feat", "feature" → Added
- Keywords: "fix", "bug", "patch" → Fixed
- Keywords: "security", "cve" → Security
- Default: Changed

---

## Usage

### For Contributors

1. **Create PR with descriptive title** (used in release notes):
   ```
   Add trailing stop loss feature (#45)
   ```

2. **Add at least one category label**:
   - `enhancement` for new features
   - `bug` for fixes
   - `security` for security patches
   - `refactor` for code improvements
   - `docs` for documentation

3. **Add risk/impact labels** (optional but recommended):
   - `risk:low` / `risk:med` / `risk:high`
   - `impact:low` / `impact:med` / `impact:high`

4. **Merge to staging** → Release notes auto-generate

### For Maintainers

#### Manual Generation
```bash
# Generate release notes since last tag
python scripts/release_notes.py

# Generate since specific date
python scripts/release_notes.py --since 2025-01-01

# Dry run (show changes without writing)
python scripts/release_notes.py --dry-run
```

#### Creating a Release

1. **Review Unreleased section** in CHANGELOG.md
2. **Create release tag:**
   ```bash
   git tag -a v1.2.0 -m "Release 1.2.0"
   git push origin v1.2.0
   ```
3. **Update CHANGELOG.md manually** to move Unreleased → versioned section:
   ```markdown
   ## [Unreleased]
   
   ## [1.2.0] - 2025-01-20
   ### Added
   - Trailing stop loss (#45)
   - Multi-session aggregator (#44)
   ...
   ```
4. **Create GitHub Release** with tag and copy/paste changelog section

#### Fixing Categorization

If a PR is miscategorized:
1. Add/fix labels on the merged PR
2. Re-run `python scripts/release_notes.py`
3. Commit updated CHANGELOG.md

---

## Troubleshooting

### "No PRs found since last release"
- **Cause:** No git tags exist or all commits are unlabeled
- **Fix:** Create initial tag `git tag v0.1.0 HEAD~10 && git push origin v0.1.0`

### "GitHub CLI not authenticated"
- **Cause:** `gh` command not configured
- **Fix:** Run `gh auth login` and authenticate with repo access

### Changes not appearing in CHANGELOG
- **Cause:** Commit message doesn't include PR number `(#123)`
- **Fix:** Use squash merge with PR number or manually add entry

### Workflow fails with "Permission denied"
- **Cause:** GITHUB_TOKEN lacks write permissions
- **Fix:** Check `.github/workflows/release_notes.yml` has:
  ```yaml
  permissions:
    contents: write
  ```

---

## Best Practices

1. **Always squash merge PRs** to keep clean git history
2. **Include PR number in merge commit** via GitHub's auto-generated message
3. **Label PRs before merging** for accurate categorization
4. **Review Unreleased section** before creating releases
5. **Keep categories focused:**
   - Added = user-facing new features
   - Fixed = user-facing bug fixes
   - Changed = breaking changes or refactors
   - Security = vulnerability patches

---

## Examples

### Good PR Titles
✅ `Add parameter drift monitoring (#6)`  
✅ `Fix race condition in order execution (#42)`  
✅ `Refactor risk engine for better testability (#38)`  

### Bad PR Titles
❌ `Update files` (no context)  
❌ `PR from feat/branch` (automated, not descriptive)  
❌ `Fixes` (too vague)

### Good Labels
✅ `enhancement` + `impact:med` + `risk:low`  
✅ `bug` + `priority:high`  
✅ `security` + `risk:high`

### Bad Labels
❌ No labels (falls back to commit message parsing)  
❌ Only `wip` or `do-not-merge` (no category)

---

## Maintenance

The release notes system is **self-documenting** and requires minimal maintenance:

- **Weekly:** Review Unreleased section for accuracy
- **Per Release:** Move Unreleased → versioned section manually
- **Quarterly:** Audit label usage for consistency

For issues or improvements, see `TECH_DEBT_REPORT.md` Section 10 (Documentation).

---

## References

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
