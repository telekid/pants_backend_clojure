"""Tests for non-Clojure ClasspathEntryRequest targets in deploy jars.

Verifies that custom targets registering a ClasspathEntryRequest (e.g., tailwind_css)
are included in the deploy jar classpath when listed as dependencies. This tests the
fix for the moved_fields issue where Pants resource generator targets hide dependencies
from the CoarsenedTarget graph used by the classpath resolver.
"""

from __future__ import annotations

import io
import itertools
import shlex
import zipfile
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from textwrap import dedent

import pytest
from pants.build_graph.address import Address
from pants.core.goals.package import BuiltPackage
from pants.core.util_rules import (
    config_files,
    external_tool,
    source_files,
    stripped_source_files,
    system_binaries,
)
from pants.core.util_rules.system_binaries import BashBinary, TouchBinary, ZipBinary
from pants.engine.fs import CreateDigest, DigestContents, FileContent, MergeDigests
from pants.engine.intrinsics import create_digest, merge_digests
from pants.engine.process import Process, execute_process_or_raise
from pants.engine.rules import QueryRule, implicitly, rule
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    Dependencies,
    FieldSet,
    SingleSourceField,
    StringField,
    Target,
)
from pants.engine.unions import UnionRule
from pants.jvm import classpath, compile, jvm_common, non_jvm_dependencies
from pants.jvm.compile import (
    ClasspathDependenciesRequest,
    ClasspathEntry,
    ClasspathEntryRequest,
    ClasspathEntryRequests,
    CompileResult,
    FallibleClasspathEntries,
    FallibleClasspathEntry,
    compile_classpath_entries,
)
from pants.jvm.goals import lockfile
from pants.jvm.resolve import coursier_fetch, jvm_tool
from pants.jvm.resolve.coursier_setup import rules as coursier_setup_rules
from pants.jvm.subsystems import JvmSubsystem
from pants.jvm.target_types import JvmArtifactTarget
from pants.jvm.util_rules import rules as jdk_util_rules
from pants.testutil.rule_runner import PYTHON_BOOTSTRAP_ENV, RuleRunner
from pants.util.logging import LogLevel
from pants_backend_clojure import compile_clj
from pants_backend_clojure.goals.package import ClojureDeployJarFieldSet
from pants_backend_clojure.goals.package import rules as package_rules
from pants_backend_clojure.namespace_analysis import rules as namespace_analysis_rules
from pants_backend_clojure.provided_dependencies import (
    rules as provided_dependencies_rules,
)
from pants_backend_clojure.subsystems.tools_build import rules as tools_build_rules
from pants_backend_clojure.target_types import (
    ClojureDeployJarTarget,
    ClojureSourceTarget,
)
from pants_backend_clojure.target_types import rules as target_types_rules
from pants_backend_clojure.tools_build_uberjar import (
    rules as tools_build_uberjar_rules,
)
from tests.clojure_test_fixtures import CLOJURE_3RDPARTY_BUILD, CLOJURE_LOCKFILE

# ---------------------------------------------------------------------------
# Mock custom ClasspathEntryRequest target (simulates tailwind_css, etc.)
# ---------------------------------------------------------------------------


class MockAssetSourceField(SingleSourceField):
    alias = "source"
    expected_file_extensions = (".txt",)
    uses_source_roots = False


class MockAssetOutputPathField(StringField):
    alias = "output_path"
    required = True


class MockAssetTarget(Target):
    alias = "mock_asset"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        MockAssetSourceField,
        MockAssetOutputPathField,
        Dependencies,
    )


@dataclass(frozen=True)
class MockAssetFieldSet(FieldSet):
    required_fields = (MockAssetSourceField,)
    sources: MockAssetSourceField
    output_path: MockAssetOutputPathField


class MockAssetClasspathEntryRequest(ClasspathEntryRequest):
    field_sets = (MockAssetFieldSet,)


@rule(desc="Compile mock asset for classpath", level=LogLevel.DEBUG)
async def compile_mock_asset(
    request: MockAssetClasspathEntryRequest,
    zip_binary: ZipBinary,
    bash: BashBinary,
    touch: TouchBinary,
    jvm: JvmSubsystem,
) -> FallibleClasspathEntry:
    """Produces a JAR containing a single file at the output_path."""
    # Resolve dependency classpath
    optional_prereq = [*((request.prerequisite,) if request.prerequisite else ())]
    fallibles = (
        await compile_classpath_entries(ClasspathEntryRequests(optional_prereq)),
        await compile_classpath_entries(**implicitly(ClasspathDependenciesRequest(request, ignore_generated=True))),
    )
    dep_classpath = FallibleClasspathEntries(itertools.chain(*fallibles)).if_all_succeeded()
    if dep_classpath is None:
        return FallibleClasspathEntry(
            description=str(request.component),
            result=CompileResult.DEPENDENCY_FAILED,
            output=None,
            exit_code=1,
        )

    target = request.component.representative
    output_path = target[MockAssetOutputPathField].value

    # Create a simple output file (simulates CSS compilation etc.)
    content_digest = await create_digest(CreateDigest([FileContent(output_path, b"/* compiled asset */\n")]))

    # Package into JAR
    output_filename = f"{request.component.representative.address.path_safe_spec}.asset.jar"
    css_paths = {Path(output_path)}
    directories = {parent for path in css_paths for parent in path.parents}
    input_files = {str(p) for p in chain(css_paths, directories)}
    input_filenames = shlex.join(sorted(input_files))

    jar_result = await execute_process_or_raise(
        **implicitly(
            Process(
                argv=[
                    bash.path,
                    "-c",
                    " ".join(
                        [
                            "TZ=UTC",
                            touch.path,
                            "-t",
                            "198001010000.00",
                            input_filenames,
                            "&&",
                            "TZ=UTC",
                            zip_binary.path,
                            "-oX",
                            output_filename,
                            input_filenames,
                        ]
                    ),
                ],
                description=f"Build mock asset JAR for {request.component}",
                input_digest=content_digest,
                output_files=[output_filename],
            )
        )
    )

    cpe = ClasspathEntry(jar_result.output_digest, [output_filename], [])
    merged_digest = await merge_digests(MergeDigests(chain((cpe.digest,), (e.digest for e in dep_classpath))))
    merged_cpe = ClasspathEntry.merge(digest=merged_digest, entries=[cpe, *dep_classpath])
    return FallibleClasspathEntry(output_filename, CompileResult.SUCCEEDED, merged_cpe, 0)


def mock_asset_rules():
    return [
        compile_mock_asset,
        *compile.rules(),
        UnionRule(ClasspathEntryRequest, MockAssetClasspathEntryRequest),
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_JVM_RESOLVES = {"java17": "locks/jvm/java17.lock.jsonc"}


@pytest.fixture
def rule_runner() -> RuleRunner:
    return RuleRunner(
        preserve_tmpdirs=True,
        target_types=[
            ClojureSourceTarget,
            ClojureDeployJarTarget,
            JvmArtifactTarget,
            MockAssetTarget,
        ],
        rules=[
            *package_rules(),
            *tools_build_rules(),
            *tools_build_uberjar_rules(),
            *namespace_analysis_rules(),
            *provided_dependencies_rules(),
            *classpath.rules(),
            *compile_clj.rules(),
            *config_files.rules(),
            *coursier_fetch.rules(),
            *coursier_setup_rules(),
            *external_tool.rules(),
            *jdk_util_rules(),
            *jvm_common.rules(),
            *jvm_tool.rules(),
            *lockfile.rules(),
            *non_jvm_dependencies.rules(),
            *source_files.rules(),
            *stripped_source_files.rules(),
            *system_binaries.rules(),
            *target_types_rules(),
            *mock_asset_rules(),
            QueryRule(BuiltPackage, [ClojureDeployJarFieldSet]),
        ],
    )


def setup_rule_runner(rule_runner: RuleRunner) -> None:
    rule_runner.set_options(
        [
            f"--jvm-resolves={repr(_JVM_RESOLVES)}",
            "--jvm-default-resolve=java17",
        ],
        env_inherit=PYTHON_BOOTSTRAP_ENV,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_deploy_jar_includes_custom_classpath_entry_target(
    rule_runner: RuleRunner,
) -> None:
    """A mock_asset target (custom ClasspathEntryRequest) listed as a dependency
    of a clojure_deploy_jar should have its output included in the final JAR.

    This is the core scenario that was broken before the fix: non-Clojure targets
    with a registered ClasspathEntryRequest were silently excluded from the classpath
    because package.py only passed Clojure source addresses to classpath_get().
    """
    setup_rule_runner(rule_runner)
    rule_runner.write_files(
        {
            "locks/jvm/java17.lock.jsonc": CLOJURE_LOCKFILE,
            "3rdparty/jvm/BUILD": CLOJURE_3RDPARTY_BUILD,
            "src/css/BUILD": dedent(
                """\
                mock_asset(
                    name="build-css",
                    source="input.txt",
                    output_path="app/style.css",
                )
                """
            ),
            "src/css/input.txt": "/* source */\n",
            "src/app/BUILD": dedent(
                """\
                clojure_source(
                    name="core",
                    source="core.clj",
                    dependencies=["3rdparty/jvm:org.clojure_clojure"],
                )

                clojure_deploy_jar(
                    name="app",
                    main="app.core",
                    dependencies=[":core", "src/css:build-css"],
                )
                """
            ),
            "src/app/core.clj": dedent(
                """\
                (ns app.core
                  (:gen-class))

                (defn -main [& args]
                  (println "Hello"))
                """
            ),
        }
    )

    target = rule_runner.get_target(Address("src/app", target_name="app"))
    field_set = ClojureDeployJarFieldSet.create(target)
    result = rule_runner.request(BuiltPackage, [field_set])

    assert len(result.artifacts) == 1

    # Extract JAR and verify the mock asset output is present
    jar_digest_contents = rule_runner.request(DigestContents, [result.digest])
    jar_path = result.artifacts[0].relpath
    jar_content = None
    for file_content in jar_digest_contents:
        if file_content.path == jar_path:
            jar_content = file_content.content
            break

    assert jar_content is not None, f"Could not find JAR at {jar_path}"

    with zipfile.ZipFile(io.BytesIO(jar_content), "r") as jar:
        entries = set(jar.namelist())

    assert "app/style.css" in entries, (
        f"Custom ClasspathEntryRequest target output 'app/style.css' not found in JAR. Entries: {sorted(entries)}"
    )


def test_deploy_jar_without_custom_target_still_works(
    rule_runner: RuleRunner,
) -> None:
    """A deploy jar with no custom ClasspathEntryRequest targets should still
    package correctly (regression guard)."""
    setup_rule_runner(rule_runner)
    rule_runner.write_files(
        {
            "locks/jvm/java17.lock.jsonc": CLOJURE_LOCKFILE,
            "3rdparty/jvm/BUILD": CLOJURE_3RDPARTY_BUILD,
            "src/app/BUILD": dedent(
                """\
                clojure_source(
                    name="core",
                    source="core.clj",
                    dependencies=["3rdparty/jvm:org.clojure_clojure"],
                )

                clojure_deploy_jar(
                    name="app",
                    main="app.core",
                    dependencies=[":core"],
                )
                """
            ),
            "src/app/core.clj": dedent(
                """\
                (ns app.core
                  (:gen-class))

                (defn -main [& args]
                  (println "Hello"))
                """
            ),
        }
    )

    target = rule_runner.get_target(Address("src/app", target_name="app"))
    field_set = ClojureDeployJarFieldSet.create(target)
    result = rule_runner.request(BuiltPackage, [field_set])

    assert len(result.artifacts) == 1
    assert result.artifacts[0].relpath.endswith(".jar")


def test_source_only_deploy_jar_includes_custom_classpath_entry_target(
    rule_runner: RuleRunner,
) -> None:
    """The source-only JAR path (main="clojure.main") should also include
    custom ClasspathEntryRequest target outputs in the final JAR.

    This covers the other branch in package.py — source files are packaged
    directly via Python zipfile rather than delegating to tools.build.
    """
    setup_rule_runner(rule_runner)
    rule_runner.write_files(
        {
            "locks/jvm/java17.lock.jsonc": CLOJURE_LOCKFILE,
            "3rdparty/jvm/BUILD": CLOJURE_3RDPARTY_BUILD,
            "src/css/BUILD": dedent(
                """\
                mock_asset(
                    name="build-css",
                    source="input.txt",
                    output_path="app/style.css",
                )
                """
            ),
            "src/css/input.txt": "/* source */\n",
            "src/app/BUILD": dedent(
                """\
                clojure_source(
                    name="core",
                    source="core.clj",
                    dependencies=["3rdparty/jvm:org.clojure_clojure"],
                )

                clojure_deploy_jar(
                    name="app",
                    main="clojure.main",
                    dependencies=[":core", "src/css:build-css"],
                )
                """
            ),
            "src/app/core.clj": dedent(
                """\
                (ns app.core)

                (defn -main [& args]
                  (println "Hello"))
                """
            ),
        }
    )

    target = rule_runner.get_target(Address("src/app", target_name="app"))
    field_set = ClojureDeployJarFieldSet.create(target)
    result = rule_runner.request(BuiltPackage, [field_set])

    assert len(result.artifacts) == 1

    # Extract JAR and verify contents
    jar_digest_contents = rule_runner.request(DigestContents, [result.digest])
    jar_path = result.artifacts[0].relpath
    jar_content = None
    for file_content in jar_digest_contents:
        if file_content.path == jar_path:
            jar_content = file_content.content
            break

    assert jar_content is not None, f"Could not find JAR at {jar_path}"

    with zipfile.ZipFile(io.BytesIO(jar_content), "r") as jar:
        entries = set(jar.namelist())

    assert "app/style.css" in entries, (
        f"Custom ClasspathEntryRequest target output 'app/style.css' not found in JAR. Entries: {sorted(entries)}"
    )
    assert "app/core.clj" in entries, f"Source file 'app/core.clj' not found in JAR. Entries: {sorted(entries)}"
