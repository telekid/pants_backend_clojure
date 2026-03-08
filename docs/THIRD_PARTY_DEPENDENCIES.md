# Third-Party Clojure Dependency Inference

## Overview

The Clojure Pants backend supports **automatic dependency inference for third-party Clojure libraries**. When you require a namespace from a third-party JAR (like `[clojure.data.json :as json]`), Pants automatically infers the dependency on the corresponding `jvm_artifact` target.

This eliminates the need to manually specify `dependencies` in your BUILD files for third-party Clojure libraries!

## Quick Start

### Step 1: Generate Lock Files

Ensure you have JVM lockfiles generated for your project:

```bash
pants generate-lockfiles ::
```

This creates lockfiles like:
```
3rdparty/jvm/default.lock
3rdparty/jvm/java17.lock
```

Third-party dependency inference works automatically after this step — no additional commands needed. Pants analyzes the JARs in your lockfiles at build time to discover which Clojure namespaces they provide.

### Step 2: Write Clojure Code

Now you can require third-party namespaces without manual dependencies:

```clojure
(ns myproject.api
  (:require [clojure.data.json :as json]       ; Auto-inferred!
            [clojure.tools.logging :as log]))   ; Auto-inferred!

(defn process-request [data]
  (log/info "Processing request")
  (json/write-str data))
```

### Step 3: No BUILD File Changes Needed!

**Before** (manual dependencies required):
```python
clojure_source(
    name="api",
    source="api.clj",
    dependencies=[
        "3rdparty/jvm:data-json",      # Had to specify manually
        "3rdparty/jvm:tools-logging",  # Had to specify manually
    ],
)
```

**After** (automatic inference):
```python
clojure_source(
    name="api",
    source="api.clj",
    # No dependencies field needed!
)
```

Or even simpler with the generator target:
```python
# BUILD file
clojure_sources()  # That's it!
```

### Step 4: Build/Test as Normal

```bash
pants check ::
pants test ::
pants package ::
```

Dependencies are automatically inferred!

## How It Works

### Architecture

1. **JAR Analysis** - At build time, Pants analyzes each JAR in your lockfiles to extract Clojure namespaces
2. **Dependency Inference** - When you build/test, Pants uses this analysis to automatically infer third-party dependencies

### Resolution Strategy

When you require a namespace, Pants follows this resolution order:

1. **First-party sources** - Checks if you have a local `.clj` file for that namespace
2. **Manual `packages` field** - Checks explicit namespace declarations on `jvm_artifact` targets
3. **Automatic JAR analysis** - Falls back to namespace mappings discovered from lockfile JARs
4. **Not found** - If none match, no dependency is inferred (will error at runtime)

This ensures that **local code always takes precedence** over third-party libraries.

## Advanced Features

### Multiple Resolves

If you use multiple JVM resolves (e.g., for different Java versions), the system handles them automatically:

```python
# pants.toml
[jvm]
resolves = { default = "3rdparty/jvm/default.lock", java17 = "3rdparty/jvm/java17.lock" }
```

Each resolve gets its own namespace mappings, so you can have different versions of the same library in different resolves.

### Manual Namespace Declarations

You can explicitly declare which namespaces an artifact provides using the `packages` field:

```python
jvm_artifact(
    name="cheshire",
    group="cheshire",
    artifact="cheshire",
    version="5.11.0",
    packages=["cheshire.**"],  # Matches cheshire and all sub-namespaces
)
```

This is useful for:
- Overriding automatic analysis results
- Disambiguating when multiple artifacts provide the same namespace
- Libraries that don't ship with Clojure source files

### AOT-Compiled JARs

The system supports both source JARs and AOT-compiled JARs:

- **Source JARs** (`.clj`, `.cljc`, `.clje`) - Namespaces are extracted by parsing the `(ns ...)` declarations
- **AOT-compiled JARs** (only `.class` files) - Namespaces are inferred from class file paths

This means it works with any Clojure library, whether it ships with source or only compiled bytecode.

### Ambiguous Namespaces

If multiple artifacts provide the same namespace (rare but possible), Pants will warn you:

```
WARNING: The target //src:api has ambiguous dependency:
  Namespace 'com.example.util' is provided by:
    - 3rdparty/jvm:lib-a
    - 3rdparty/jvm:lib-b

Please specify which one explicitly in dependencies=[...].
```

**Resolution:** Add an explicit dependency in your BUILD file:
```python
clojure_source(
    name="api",
    source="api.clj",
    dependencies=["3rdparty/jvm:lib-a"],  # Explicit choice
)
```

## Troubleshooting

### Namespace not being inferred

**Checklist:**
1. Is the artifact in your lockfile? Check `3rdparty/jvm/*.lock`
2. Have you run `pants generate-lockfiles` after adding the dependency?
3. Is there a first-party file with the same namespace? (First-party takes precedence)

### When to regenerate lockfiles

You should regenerate lockfiles when:

1. **Adding new dependencies** - Run `pants generate-lockfiles`
2. **Updating dependency versions** - Same as above
3. **Changing resolves** - If you modify your `jvm.resolves` configuration

## Examples

### Example 1: Simple API with JSON

```clojure
(ns myproject.api
  (:require [clojure.data.json :as json]))

(defn handler [request]
  {:status 200
   :body (json/write-str {:result "success"})})
```

**No BUILD file needed** (with `clojure_sources()` generator target)

### Example 2: Mixed First-Party and Third-Party

```clojure
(ns myproject.service
  (:require [myproject.util :as util]           ; First-party - inferred
            [clojure.data.json :as json]         ; Third-party - inferred
            [clojure.tools.logging :as log]))    ; Third-party - inferred

(defn process [data]
  (log/info "Processing" data)
  (util/validate data)
  (json/write-str data))
```

**BUILD file:**
```python
clojure_sources()  # All dependencies inferred automatically!
```

### Example 3: Multiple Namespaces from One Artifact

```clojure
(ns myproject.async
  (:require [clojure.core.async :as async]
            [clojure.core.async.impl.protocols :as protocols]))

(defn setup []
  (async/chan 10))
```

Both `clojure.core.async` and `clojure.core.async.impl.protocols` map to the same `core-async` artifact, so only one dependency is inferred.

## Comparison with deps.edn

If you're coming from a `deps.edn` workflow:

| Feature | deps.edn | Pants |
|---------|----------|-------|
| Third-party deps | Automatic | Automatic |
| First-party deps | Manual (aliases) | Automatic |
| Dependency management | git deps, Maven | Coursier lockfiles |
| Multi-project | Requires configuration | Built-in monorepo support |
| Incremental builds | Limited | Full dependency graph |
