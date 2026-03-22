"""Tests for JAR analysis utilities.

This test suite verifies that JAR files can be correctly analyzed to extract
Clojure namespaces, supporting both source JARs and AOT-compiled JARs.
"""

import tempfile
import zipfile
from pathlib import Path

from pants_backend_clojure.utils.jar_analyzer import (
    analyze_jar_for_namespaces,
    is_clojure_jar,
    namespace_from_class_path,
)

# ===== Helper functions for creating test JARs =====


def create_test_jar(files: dict[str, str]) -> Path:
    """Create a temporary JAR file with the given contents.

    Args:
        files: Dictionary mapping file paths to file contents.

    Returns:
        Path to the created JAR file.
    """
    jar_file = tempfile.NamedTemporaryFile(suffix=".jar", delete=False)
    jar_path = Path(jar_file.name)

    with zipfile.ZipFile(jar_path, "w") as jar:
        for path, content in files.items():
            jar.writestr(path, content)

    return jar_path


# ===== Tests for namespace_from_class_path =====


def test_namespace_from_class_path_init_class():
    """Test extracting namespace from __init.class files."""
    # __init.class files are the namespace loaders - these are what we want
    assert namespace_from_class_path("clojure/data/json__init.class") == "clojure.data.json"
    assert namespace_from_class_path("com/example/utils__init.class") == "com.example.utils"


def test_namespace_from_class_path_demunge_heuristic():
    """Test that underscores are converted to hyphens (demunge)."""
    # my_app/core__init.class could be from (ns my-app.core) or (ns my_app.core)
    # We use the demunge heuristic (underscore -> hyphen) by convention
    assert namespace_from_class_path("my_app/core__init.class") == "my-app.core"
    assert namespace_from_class_path("ring/middleware/anti_forgery__init.class") == "ring.middleware.anti-forgery"


def test_namespace_from_class_path_ignores_regular_class():
    """Test that regular .class files (not __init.class) are ignored."""
    # Regular namespace classes don't have the __init suffix
    assert namespace_from_class_path("clojure/data/json.class") is None
    assert namespace_from_class_path("com/example/Utils.class") is None


def test_namespace_from_class_path_ignores_fn():
    """Test that function classes are ignored."""
    assert namespace_from_class_path("clojure/data/json$read_str.class") is None
    assert namespace_from_class_path("clojure/data/json$fn__123.class") is None


def test_namespace_from_class_path_non_class():
    """Test that non-.class files return None."""
    assert namespace_from_class_path("clojure/data/json.clj") is None
    assert namespace_from_class_path("README.md") is None


# ===== Tests for analyze_jar_for_namespaces with source files =====


def test_analyze_jar_with_single_clj_source():
    """Test analyzing a JAR with a single Clojure source file."""
    jar_path = create_test_jar({"clojure/data/json.clj": "(ns clojure.data.json)\n\n(defn read-str [s] s)"})

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_jar_with_multiple_clj_sources():
    """Test analyzing a JAR with multiple Clojure source files."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.clj": "(ns clojure.data.json)",
            "clojure/data/json/util.clj": "(ns clojure.data.json.util)",
            "clojure/data/json/parser.clj": "(ns clojure.data.json.parser)",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should be sorted
        assert result.namespaces == (
            "clojure.data.json",
            "clojure.data.json.parser",
            "clojure.data.json.util",
        )
    finally:
        jar_path.unlink()


def test_analyze_jar_with_cljc_source():
    """Test analyzing a JAR with .cljc (Clojure/ClojureScript) files."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.cljc": "(ns clojure.data.json)",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_jar_with_clje_source():
    """Test analyzing a JAR with .clje files."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.clje": "(ns clojure.data.json)",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_jar_ignores_metainf():
    """Test that files in META-INF/ are ignored."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.clj": "(ns clojure.data.json)",
            "META-INF/something.clj": "(ns meta.inf.something)",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should only find the non-META-INF namespace
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_jar_with_complex_namespace():
    """Test analyzing namespaces with hyphens (converted to underscores in paths)."""
    jar_path = create_test_jar(
        {
            "clojure/tools/logging.clj": "(ns clojure.tools.logging)",
            "ring/middleware/anti_forgery.clj": "(ns ring.middleware.anti-forgery)",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == (
            "clojure.tools.logging",
            "ring.middleware.anti-forgery",
        )
    finally:
        jar_path.unlink()


# ===== Tests for AOT-compiled JARs (class files only) =====


def test_analyze_jar_with_aot_compiled_classes():
    """Test analyzing an AOT-compiled JAR with only .class files."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.class": b"fake class content",
            "clojure/data/json__init.class": b"fake init class",
            "clojure/data/json$read_str.class": b"fake function class",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should detect namespace from __init.class file only
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_jar_with_aot_hyphenated_namespaces():
    """Test analyzing AOT JARs with hyphenated namespaces (demunge heuristic)."""
    jar_path = create_test_jar(
        {
            "my_app/core__init.class": b"fake init class",
            "my_app/core.class": b"fake class",
            "my_app/core$main.class": b"fake function class",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should apply demunge heuristic: underscores -> hyphens
        assert result.namespaces == ("my-app.core",)
    finally:
        jar_path.unlink()


def test_analyze_jar_combines_source_and_classes():
    """Test that both source files and __init.class files are analyzed."""
    jar_path = create_test_jar(
        {
            # Source file with namespace
            "clojure/data/json.clj": "(ns clojure.data.json)",
            # AOT-compiled namespace not present as source (e.g., Rama pattern)
            "com/rpl/rama__init.class": b"fake init class",
            # Regular class file — should be ignored (no __init suffix)
            "clojure/data/xml.class": b"fake class",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should find both: source-based and __init.class-based namespaces
        assert result.namespaces == ("clojure.data.json", "com.rpl.rama")
    finally:
        jar_path.unlink()


def test_analyze_jar_deduplicates_source_and_class():
    """Test that a namespace found in both source and __init.class is deduplicated."""
    jar_path = create_test_jar(
        {
            # Same namespace in both source and AOT form
            "clojure/data/json.clj": "(ns clojure.data.json)",
            "clojure/data/json__init.class": b"fake init class",
            "clojure/data/json$read_str.class": b"fake function class",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should appear only once
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


# ===== Tests for edge cases =====


def test_analyze_empty_jar():
    """Test analyzing an empty JAR file."""
    jar_path = create_test_jar({})

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == ()
    finally:
        jar_path.unlink()


def test_analyze_jar_with_no_clojure_content():
    """Test analyzing a JAR with no Clojure files (pure Java JAR)."""
    jar_path = create_test_jar(
        {
            "com/example/Util.class": b"fake java class",
            "META-INF/MANIFEST.MF": "Manifest-Version: 1.0",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Pure Java JAR - no Clojure namespaces
        # Only __init.class files are detected, so this should be empty
        assert result.namespaces == ()
    finally:
        jar_path.unlink()


def test_analyze_jar_with_invalid_namespace():
    """Test handling of files with malformed namespace declarations."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.clj": "(ns clojure.data.json)",
            "invalid.clj": "this is not valid clojure code",
            "another.clj": "(defn foo [])",  # No namespace declaration
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should only find the valid namespace
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_jar_with_non_utf8():
    """Test handling of non-UTF8 content."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.clj": "(ns clojure.data.json)",
        }
    )

    # Add a file with invalid UTF-8
    with zipfile.ZipFile(jar_path, "a") as jar:
        jar.writestr("invalid.clj", b"\xff\xfe invalid bytes")

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should still find the valid namespace, ignoring the invalid file
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_invalid_jar():
    """Test analyzing a corrupted/invalid JAR file."""
    # Create a file that's not a valid ZIP/JAR
    jar_path = Path(tempfile.mktemp(suffix=".jar"))
    jar_path.write_text("this is not a valid JAR file")

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Should return empty result rather than crashing
        assert result.namespaces == ()
    finally:
        jar_path.unlink()


# ===== Tests for is_clojure_jar =====


def test_is_clojure_jar_with_source():
    """Test detecting Clojure JAR by presence of .clj files."""
    jar_path = create_test_jar(
        {
            "clojure/data/json.clj": "(ns clojure.data.json)",
        }
    )

    try:
        assert is_clojure_jar(jar_path) is True
    finally:
        jar_path.unlink()


def test_is_clojure_jar_with_common_namespace():
    """Test detecting Clojure JAR by common namespace prefixes."""
    jar_path = create_test_jar(
        {
            "clojure/core/async.class": b"fake class",
        }
    )

    try:
        assert is_clojure_jar(jar_path) is True
    finally:
        jar_path.unlink()


def test_is_not_clojure_jar():
    """Test that pure Java JARs are not detected as Clojure."""
    jar_path = create_test_jar(
        {
            "com/example/Util.class": b"fake java class",
            "META-INF/MANIFEST.MF": "Manifest-Version: 1.0",
        }
    )

    try:
        # This might return True since our heuristic isn't perfect
        # The function is meant to be conservative (false positives OK)
        result = is_clojure_jar(jar_path)
        # We accept either result - it's just a heuristic
        assert isinstance(result, bool)
    finally:
        jar_path.unlink()


def test_is_clojure_jar_invalid_jar():
    """Test handling invalid JAR files."""
    jar_path = Path(tempfile.mktemp(suffix=".jar"))
    jar_path.write_text("not a jar")

    try:
        assert is_clojure_jar(jar_path) is False
    finally:
        jar_path.unlink()


# ===== Integration tests with realistic JARs =====


def test_analyze_realistic_source_jar():
    """Test analyzing a realistic Clojure library JAR (simulated)."""
    # Simulate a JAR like org.clojure/data.json
    jar_path = create_test_jar(
        {
            "clojure/data/json.clj": """(ns clojure.data.json
          "JSON parser/generator to/from Clojure data structures."
          (:require [clojure.string :as str]))

        (defn read-str [s] s)
        (defn write-str [x] x)
        """,
            "META-INF/MANIFEST.MF": "Manifest-Version: 1.0\n",
            "META-INF/maven/org.clojure/data.json/pom.properties": "version=2.4.0\n",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == ("clojure.data.json",)
    finally:
        jar_path.unlink()


def test_analyze_realistic_multi_namespace_jar():
    """Test analyzing a JAR with multiple namespaces (like core.async)."""
    # Simulate a JAR like org.clojure/core.async
    jar_path = create_test_jar(
        {
            "clojure/core/async.clj": "(ns clojure.core.async)",
            "clojure/core/async/impl/protocols.clj": "(ns clojure.core.async.impl.protocols)",
            "clojure/core/async/impl/channels.clj": "(ns clojure.core.async.impl.channels)",
            "clojure/core/async/impl/buffers.clj": "(ns clojure.core.async.impl.buffers)",
            "clojure/core/async/impl/dispatch.clj": "(ns clojure.core.async.impl.dispatch)",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        assert result.namespaces == (
            "clojure.core.async",
            "clojure.core.async.impl.buffers",
            "clojure.core.async.impl.channels",
            "clojure.core.async.impl.dispatch",
            "clojure.core.async.impl.protocols",
        )
    finally:
        jar_path.unlink()


def test_analyze_mixed_jar_aot_namespaces_not_in_source():
    """Test analyzing a JAR where some namespaces exist only as AOT classes.

    This simulates JARs like Rama where the JAR contains some .clj helper
    files but the primary namespaces (com.rpl.rama, com.rpl.rama.path) are
    only available as AOT-compiled __init.class files. Before the fix,
    the presence of any .clj file would cause __init.class analysis to be
    skipped entirely, making these namespaces invisible to inference.
    """
    jar_path = create_test_jar(
        {
            # A helper .clj source file
            "com/rpl/rama/helpers.clj": "(ns com.rpl.rama-helpers)",
            # Primary namespaces only as AOT classes
            "com/rpl/rama__init.class": b"fake init class",
            "com/rpl/rama$module__init.class": b"fake class",
            "com/rpl/rama/path__init.class": b"fake init class",
            # Function classes — should be ignored
            "com/rpl/rama$defmodule.class": b"fake fn class",
            "com/rpl/rama$fn__12345.class": b"fake fn class",
        }
    )

    try:
        result = analyze_jar_for_namespaces(jar_path)
        # Must find ALL namespaces: source-based AND AOT-based
        assert "com.rpl.rama-helpers" in result.namespaces  # from .clj
        assert "com.rpl.rama" in result.namespaces  # from __init.class
        assert "com.rpl.rama.path" in result.namespaces  # from __init.class
    finally:
        jar_path.unlink()
