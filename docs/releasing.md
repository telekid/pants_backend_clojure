# Releasing pants-backend-clojure

## Overview

Releases are managed via GitHub Actions workflows:

1. **Create a draft release** via the `Create draft release` workflow
2. **Review and finalize** the draft release on GitHub
3. **Publish to PyPI** via the `Publish` workflow (Phase 4)

## Step-by-step

### 1. Bump the version

Update `PLUGIN_VERSION` in `pants-plugins/BUILD`:

```python
PLUGIN_VERSION = "0.2.0"
```

Commit and push to `main` (or your release branch). Ensure CI passes.

### 2. Create a git tag

```bash
git tag v0.2.0
git push origin v0.2.0
```

### 3. Trigger the draft release workflow

1. Go to **Actions** > **Create draft release** in the GitHub repo
2. Click **Run workflow**
3. Fill in:
   - **ref**: the tag name (e.g., `v0.2.0`)
   - **version**: the version string without the `v` prefix (e.g., `0.2.0`)
4. Click **Run workflow**

The workflow will:
- Run the full test suite
- Build the wheel and source archive
- Attest build provenance
- Create a draft GitHub release with the artifacts attached

### 4. Review the draft release

1. Go to **Releases** in the GitHub repo
2. Find the draft release
3. Review the attached artifacts (wheel and source archive)
4. Edit the release notes as needed
5. When satisfied, click **Publish release** (this removes the draft status)

### 5. Publish to PyPI

Once the release is finalized (no longer a draft), use the `Publish` workflow to push
to TestPyPI and/or production PyPI. See Phase 4 documentation for details.

## Version conventions

- Release versions: `0.2.0`, `1.0.0`
- Pre-release versions: `0.2.0rc1`, `0.2.0dev1`
  - Versions containing "dev" or "rc" are automatically marked as pre-releases on GitHub
