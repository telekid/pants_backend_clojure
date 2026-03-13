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

## Multi-Pants-version support

The plugin is tested against multiple Pants versions using per-version Python resolves.
The `pants_version` in `pants.toml` is set to the latest supported version (used to run
the build system itself), while the plugin code is tested against all supported versions
via parametrized resolves.

### Adding support for a new Pants version

1. Create `3rdparty/python/pants-X.YZ.txt` with `pantsbuild.pants==X.YZ.0`,
   `pantsbuild.pants.testutil==X.YZ.0`, `pytest`, and `packaging`
2. Add a `python_requirements` target to `3rdparty/python/BUILD` with `resolve="pants-X.YZ"`
3. Add `"pants-X.YZ" = "3rdparty/python/pants-X.YZ.lock"` to `[python.resolves]` in `pants.toml`
4. Add `**parametrize("pants-X.YZ", resolve="pants-X.YZ")` to all parametrized targets in
   `pants-plugins/BUILD`
5. Generate the lock file: `pants generate-lockfiles --resolve=pants-X.YZ`
6. Bump `pants_version` and `default_resolve` in `pants.toml` to the new version
7. Run tests, fix any API incompatibilities
8. Update CI cache hash references if needed

### Dropping support for an old Pants version

1. Remove the resolve from `[python.resolves]` in `pants.toml`
2. Remove the requirements file (`3rdparty/python/pants-X.YZ.txt`) and lock file
3. Remove the `python_requirements` target from `3rdparty/python/BUILD`
4. Remove the `**parametrize("pants-X.YZ", ...)` entry from all targets in `pants-plugins/BUILD`
5. Clean up any version-conditional code that's no longer needed
6. If the dropped version was used by `python_distribution`, update it to a new lower bound

### Relationship between `pants_version` and supported versions

- `pants_version` (in `pants.toml`): The version of Pants used to run the build system
  (lint, test, package). Set to the latest supported version.
- Supported versions (resolves): The versions the plugin is tested against. The wheel is
  built using the lowest supported version's resolve, with `pantsbuild.pants` excluded
  from `install_requires`.

## Version conventions

- Release versions: `0.2.0`, `1.0.0`
- Pre-release versions: `0.2.0rc1`, `0.2.0dev1`
  - Versions containing "dev" or "rc" are automatically marked as pre-releases on GitHub
