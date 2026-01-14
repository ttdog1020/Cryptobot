# Release Notes Automation

Automatic CHANGELOG.md maintenance for the CryptoBot project.

## Overview

The `scripts/release_notes.py` script automatically updates `CHANGELOG.md` with merged PRs, categorizing them by label into [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) sections.

## Label-to-Section Mapping

| Label | CHANGELOG Section |
|-------|------------------|
| `feature`, `enhancement` | **Added** |
| `bugfix`, `bug`, `fix` | **Fixed** |
| `breaking-change`, `refactor` | **Changed** |
| `tech-debt`, `chore`, `cleanup`, `maintenance`, `documentation` | **Maintenance** |
| `removal`, `deprecation` | **Removed** |
| *(no matching label)* | **Changed** (default) |

### Maintenance Section

The **Maintenance** section captures tech-debt and housekeeping work that doesn't directly impact user-facing features:

- Refactoring and code cleanup
- Documentation updates
- Build system changes
- Test improvements
- Dependency updates

This keeps the main sections (Added/Changed/Fixed) focused on user-visible changes while still documenting all work.

## How It Works

1. **Trigger**: Runs automatically on every push to `staging` via GitHub Actions workflow
2. **Fetch PRs**: Uses `gh` CLI to get merged PRs since last tag/release
3. **Categorize**: Examines PR labels to determine changelog section
4. **Update**: Appends new entries to `[Unreleased]` section in CHANGELOG.md
5. **Commit**: Pushes updated CHANGELOG.md back to `staging` if changes detected

## Idempotency

The script is **idempotent** - running it multiple times won't create duplicate entries:

- Existing entries are parsed from CHANGELOG.md
- New entries are compared against existing ones
- Only net-new PRs are added
- Safe to run on every push

## Skipping Changelog Updates

To exclude a PR from the changelog (e.g., for minor typo fixes):

**Add label**: `no-changelog` or `skip-changelog`

Example:
```bash
gh pr edit 123 --add-label "no-changelog"
```

## Manual Usage

Run locally to preview changes:

```bash
# Dry run (no changes)
python scripts/release_notes.py --dry-run

# Update CHANGELOG.md since specific commit
python scripts/release_notes.py --since abc1234

# Update since last tag (default)
python scripts/release_notes.py
```

## Workflow Configuration

**File**: `.github/workflows/release_notes.yml`

**Permissions**:
- `contents: write` - Commits CHANGELOG updates
- `pull-requests: read` - Reads PR metadata

**Environment Variables**:
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions

## Example Output

```markdown
## [Unreleased]

### Added
- Add trailing stop-loss implementation (#45)
- Implement ML-based signal generation (#50)

### Fixed
- Fix equity calculation in paper trader (#48)
- Resolve symbol propagation bug (#49)

### Maintenance
- Archive legacy MACD parameter sweep script (#9)
- Consolidate strategy naming convention (#10)
- Delete orphaned config files (#11)
- Flatten strategies/ml_based directory (#12)
- Consolidate duplicate imports in bot.py (#13)
```

## Best Practices

1. **Label all PRs** - Ensures proper categorization
2. **Descriptive PR titles** - These become changelog entries
3. **Use semantic prefixes** - `[TECH_DEBT]`, `[BUGFIX]`, etc. (optional but helpful)
4. **Review CHANGELOG** - Verify entries after automated updates
5. **Manual edits allowed** - Script preserves manual changes via idempotent merge

## Release Process

When cutting a new release:

1. Review `[Unreleased]` section in CHANGELOG.md
2. Rename `[Unreleased]` → `[X.Y.Z] - YYYY-MM-DD`
3. Add new empty `[Unreleased]` section above
4. Tag release: `git tag vX.Y.Z`
5. Push tag: `git push origin vX.Y.Z`

Future automated runs will populate the new `[Unreleased]` section.

## Troubleshooting

**Q: Script fails with "gh: command not found"**  
A: Install GitHub CLI: https://cli.github.com/

**Q: "No PRs found" but PRs exist**  
A: Check that PRs are merged to `staging` branch (not `main`)

**Q: Duplicate entries appearing**  
A: This shouldn't happen due to idempotency. File a bug if it does.

**Q: Wrong section for my PR**  
A: Add/update the label on the PR, then rerun the script manually.

## References

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/)
- [GitHub CLI](https://cli.github.com/)
