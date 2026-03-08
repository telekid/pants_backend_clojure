# Fix `concurrently()` Argument Overflow in `generate-deps-edn`

## Problem

The `generate-deps-edn` goal fails with a `TypeError` when the combined number of
source and test targets exceeds 10. The error occurs in
`gather_clojure_sources_for_resolve()` at `generate_deps.py:271-280`.

### Root Cause

`concurrently()` (alias for Pants' `MultiGet`) supports two calling forms:

1. **Form 1 (iterable):** `concurrently(Iterable[awaitable[T]])` — a single iterable argument
2. **Form 2 (positional):** `concurrently(awaitable[T1], ..., awaitable[T10])` — up to 10 individual positional arguments

The current code uses `*` unpacking to splat two generators into individual positional arguments:

```python
all_source_files = await concurrently(
    *(determine_source_files(...) for target in source_targets),
    *(determine_source_files(...) for target in test_targets),
)
```

This triggers form 2. When `len(source_targets) + len(test_targets) > 10`, Pants
raises the `TypeError` because form 2 can't handle more than 10 arguments.

### Correct Pattern

Other call sites in this codebase (e.g., `goals/repl.py:200`) correctly use form 1 by
building a list of requests first, then passing a single generator expression to
`concurrently()`.

## Fix

### Phase 1: Fix the `concurrently()` call [DONE]

**File:** `pants-plugins/pants_backend_clojure/goals/generate_deps.py`

**Change:** Replace the `*`-unpacked positional args with a single generator expression
(form 1). Build the requests list first, then pass a generator — matching the pattern
used in `goals/repl.py:182-201`.

**Before (lines 271-280):**
```python
all_source_files = await concurrently(
    *(
        determine_source_files(SourceFilesRequest([target[ClojureSourceField]]))
        for target in source_targets
    ),
    *(
        determine_source_files(SourceFilesRequest([target[ClojureTestSourceField]]))
        for target in test_targets
    ),
)
```

**After:**
```python
source_file_requests = [
    SourceFilesRequest([t[ClojureSourceField]]) for t in source_targets
] + [
    SourceFilesRequest([t[ClojureTestSourceField]]) for t in test_targets
]

all_source_files = await concurrently(
    determine_source_files(req) for req in source_file_requests
)
```

No new imports needed.

The rest of the function (lines 282-333) does not need to change — it already uses
integer indexing with `test_offset = len(source_targets)` to split the combined
`all_source_files` tuple back into source vs test results, and `concurrently` form 1
preserves ordering.

### Phase 2: Add regression test [DONE]

**File:** `pants-plugins/tests/test_generate_deps_edn.py`

Add a test that creates >10 Clojure source targets in a single resolve to verify that
`generate-deps-edn` works with many targets. This prevents the bug from recurring.

The test should follow the pattern of `test_generate_deps_edn_multiple_sources` but
generate 11+ `clojure_source` targets, each with a distinct namespace and file.

### Phase 3: Verify [DONE]

1. Run existing tests: `pants test pants-plugins/tests/test_generate_deps_edn.py`
2. Run full plugin test suite: `pants test pants-plugins::`
