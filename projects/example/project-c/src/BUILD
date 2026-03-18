# cheshire is declared once and shared across resolves
jvm_artifact(
    name="cheshire-java17",
    group="cheshire",
    artifact="cheshire",
    version="5.13.0",
    resolve="java17",
)
jvm_artifact(
    name="cheshire-java21",
    group="cheshire",
    artifact="cheshire",
    version="5.13.0",
    resolve="java21",
)

# No explicit dependencies on cheshire — third-party inference discovers it
# automatically by analyzing JAR contents from the lockfile.
clojure_sources(name="java17",resolve="java17",sources=["**/*.clj"])
clojure_sources(name="java21",resolve="java21",sources=["**/*.clj"])