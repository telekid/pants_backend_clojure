---
name: update-release-version
description: Bump the plugin release version (major, minor, or patch) and update all references.
user_invocable: true
---

# Update Release Version

Increment the plugin version and update all references across the repository.

## Arguments

The user must specify one of: `major`, `minor`, or `patch`.

## Steps

1. **Read the current version** from `pants-plugins/BUILD` (the `PLUGIN_VERSION` line).
2. **Parse** the version as `MAJOR.MINOR.PATCH`.
3. **Compute the new version** based on the argument:
   - `major`: increment MAJOR, reset MINOR and PATCH to 0
   - `minor`: increment MINOR, reset PATCH to 0
   - `patch`: increment PATCH
4. **Update the version** in these files:
   - `pants-plugins/BUILD` — the `PLUGIN_VERSION = "..."` line
   - `README.md` — the `pants-backend-clojure==X.Y.Z` version in the install instructions
5. **Show the user** what changed (old version → new version) and which files were updated.

## Important

- Do NOT commit or push. The user will do that separately.
- Only update version strings that match the current version exactly to avoid false replacements.
