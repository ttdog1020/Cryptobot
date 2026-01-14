# GitHub Setup - Manual Steps

## Overview

After pushing the repository to GitHub, complete these manual configuration steps to enable the hands-off workflow.

**Estimated time:** 10 minutes
**Prerequisites:** Repository pushed to GitHub, branches `main` and `staging` exist

---

## Step 1: Create Branch Protection for `main`

1. Go to **Settings** → **Branches**
2. Click **Add rule** button
3. Configure:
   - **Branch name pattern:** `main`
   - **Require a pull request before merging:** ✅ YES
     - Require approvals: ✅ YES (minimum: 1)
     - Require review from Code Owners (optional)
   - **Require status checks to pass:** ✅ YES
     - Require branches to be up to date: ✅ YES
     - Status checks that must pass: Select `CI`
   - **Require conversation resolution:** ✅ YES
   - **Allow auto-merge:** ☐ NO (keep main manual)
   - **Automatically delete head branches:** ✅ YES

4. Click **Create** button

---

## Step 2: Create Branch Protection for `staging`

1. Go to **Settings** → **Branches**
2. Click **Add rule** button
3. Configure:
   - **Branch name pattern:** `staging`
   - **Require a pull request before merging:** ✅ YES (optional, but recommended)
   - **Require status checks to pass:** ✅ YES
     - Require branches to be up to date: ✅ YES
     - Status checks: `CI`
   - **Allow auto-merge:** ✅ YES
     - Auto-merge method: **Squash and merge** (recommended)
   - **Automatically delete head branches:** ✅ YES

4. Click **Create** button

---

## Step 3: Enable Auto-Merge in Repository Settings

1. Go to **Settings** → **General** (main tab)
2. Scroll to **Pull Requests** section
3. Check: ✅ **Allow auto-merge**
4. Default merge method: Select **Squash and merge**
5. Uncheck: ☐ Allow rebase merging (optional, for consistency)
6. Check: ✅ Always suggest updating pull request branches (optional)
7. Check: ✅ Automatically delete head branches (recommended)
8. Scroll down and click **Save changes**

---

## Step 4: (Optional) Add CODEOWNERS

For teams: Require approval from specific reviewers for safety-critical files.

1. Create file: `.github/CODEOWNERS`
2. Add content:
   ```
   # Execution and safety files - require approval
   execution/ @your-username
   risk_management/ @your-username
   config/trading_mode.yaml @your-username
   config/risk.json @your-username
   
   # All files default
   * @your-username
   ```
3. Commit and push to main
4. In **Settings** → **Branches** → `main` rule:
   - Check: ✅ **Require review from Code Owners**

---

## Step 5: Create Required Status Checks

CI already configured in `.github/workflows/ci.yml`, so GitHub will auto-detect when first PR runs.

**What will be required:**
- `CI` status check (from workflow)

**To verify status checks:**
1. Go to **Settings** → **Branches** → `main` or `staging` rule
2. Under "Require status checks to pass", search for and select: `CI`
3. Click **Create**

---

## Step 6: (Optional) Configure GitHub Actions Permissions

To allow auto-merge workflow:

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions:**
   - ✅ Read and write permissions
   - ☐ Allow GitHub Actions to create and approve pull requests
3. Click **Save**

---

## Step 7: (Optional) Add Secrets for Future Live Trading

When live trading is needed, add secrets to repo:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:
   - **Name:** `BINANCE_API_KEY`
     **Value:** Your Binance API key (NEVER hardcoded in code)
   - **Name:** `BINANCE_API_SECRET`
     **Value:** Your Binance secret
3. Click **Add secret**

**IMPORTANT:** These secrets will NOT be used unless:
- `config/trading_mode.yaml` has `mode: "live"`
- AND environment variable `LIVE_TRADING_ENABLED=true` is set
- The dual-key gate enforces this safety

---

## Step 8: Verify Setup

### Test Branch Protection

1. Create a test PR from feature branch to `staging`:
   ```bash
   git checkout -b test/branch-protection
   echo "test" > test.txt
   git add test.txt
   git commit -m "Test: verify branch protection"
   git push -u origin test/branch-protection
   ```

2. Open PR in GitHub (should auto-open)
3. Verify:
   - ✅ Cannot merge without CI passing (button disabled)
   - ✅ Once CI passes, merge button enables
   - ✅ Auto-merge option appears (if configured)

4. Clean up:
   ```bash
   git checkout staging
   git branch -D test/branch-protection
   ```

### Test Workflow Triggers

1. Check **Actions** tab in GitHub
2. Verify workflow runs exist for:
   - `CI` - on every PR and push to main/staging
   - `Nightly Paper Trading` - appears in scheduled runs

---

## Step 9: Configure Nightly Scheduling (Optional Customization)

If you want different nightly schedule:

1. Go to `.github/workflows/nightly_paper.yml`
2. Edit line with cron schedule:
   ```yaml
   - cron: '0 3 * * *'  # 03:00 UTC daily
   ```
3. Use [crontab.guru](https://crontab.guru) to find your time:
   - Example: `0 1 * * *` = 01:00 UTC
   - Example: `30 2 * * 1-5` = 02:30 UTC Monday-Friday

4. Commit and push to `staging`

---

## Summary Checklist

- [ ] Branch protection created for `main` (1 approval + CI required)
- [ ] Branch protection created for `staging` (CI required + auto-merge enabled)
- [ ] Auto-merge enabled in repo settings
- [ ] Status checks configured (CI)
- [ ] CODEOWNERS created (optional)
- [ ] Test PR verified branch protection works
- [ ] Workflows appear in Actions tab
- [ ] Nightly schedule verified (if customized)

---

## Verification: After First PR Merge

1. Create and merge a test PR to staging
2. Verify:
   - ✅ CI runs automatically
   - ✅ PR auto-merges when CI passes
   - ✅ No artifacts leak into repo
   - ✅ Branch gets auto-deleted

3. If nightly runs scheduled:
   - Go to Actions → Nightly Paper Trading
   - Should see scheduled runs (may wait for midnight UTC)
   - Or manually trigger: Run workflow → Run workflow

---

## Troubleshooting

### "Branch protection won't let me merge"
- Check CI status: Is `CI` check passing (green checkmark)?
- If red: Fix failing tests in the PR
- If pending: Wait for workflow to complete (~2-3 minutes)

### "Auto-merge not working"
- Verify: Auto-merge enabled in repo settings
- Verify: Status checks set to "Require" in branch protection
- Wait for CI to fully complete before auto-merge triggers

### "Nightly Paper Trading not running"
- Go to Actions → Nightly Paper Trading
- Check if scheduled runs appear (checks every day at configured time)
- Manually trigger: Click "Run workflow"
- Check logs if job fails

---

## Next Steps

1. **Read RUNBOOK.md** for development workflow
2. **Read AGENTS.md** for coding guidelines
3. **Create first feature branch** and test PR flow
4. **Set up IDE** with repo structure and linting
5. **Configure local Python environment** if not already done

---

**All set!** Your hands-off workflow is now ready. 🎉

