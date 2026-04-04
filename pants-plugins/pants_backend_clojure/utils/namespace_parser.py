"""Utilities for Clojure namespace and file path conversions.

This module provides utility functions for converting between Clojure
namespace names and file paths, as well as checking for JDK classes.

For parsing Clojure source files to extract namespaces, requires, and imports,
use the ClojureNamespaceAnalysis rule from pants_backend_clojure.namespace_analysis,
which properly invokes clj-kondo inside the Pants sandbox.
"""

from __future__ import annotations

from pants_backend_clojure.config import CLOJURE_SOURCE_EXTENSIONS


def namespace_to_paths(namespace: str) -> tuple[str, ...]:
    """Convert a Clojure namespace to all candidate file paths.

    Returns a tuple of candidate paths for each supported Clojure source extension,
    e.g. ("example/project_a/core.clj", "example/project_a/core.cljc")
    """
    stem = namespace.replace(".", "/").replace("-", "_")
    return tuple(f"{stem}{ext}" for ext in CLOJURE_SOURCE_EXTENSIONS)


def path_to_namespace(file_path: str) -> str:
    """Convert a file path to a Clojure namespace.

    Args:
        file_path: The file path (relative or absolute).

    Returns:
        The expected namespace name for the file.

    Example:
        "example/project_a/core.clj" -> "example.project-a.core"

    Note:
        Clojure uses hyphens in namespaces for underscores in file paths.
    """
    # Remove .clj or .cljc extension
    path = file_path
    if path.endswith(".clj"):
        path = path[:-4]
    elif path.endswith(".cljc"):
        path = path[:-5]

    # Convert path separators to dots and underscores to hyphens
    namespace = path.replace("/", ".").replace("_", "-")
    return namespace


def class_to_path(class_name: str) -> str:
    """Convert a Java class name to its expected file path.

    Args:
        class_name: The fully-qualified Java class name.

    Returns:
        The expected file path for the class.

    Examples:
        "com.example.Foo" -> "com/example/Foo.java"
        "java.util.HashMap" -> "java/util/HashMap.java"
        "java.util.Map$Entry" -> "java/util/Map.java" (inner class)

    Note:
        Inner classes (containing $) are mapped to their outer class file.
    """
    # Handle inner classes by taking only the outer class
    if "$" in class_name:
        class_name = class_name.split("$")[0]

    path = class_name.replace(".", "/")
    return f"{path}.java"


def is_jdk_class(class_name: str) -> bool:
    """Check if a class is part of the JDK (implicit dependency).

    Args:
        class_name: The fully-qualified Java class name.

    Returns:
        True if the class is part of the JDK, False otherwise.

    JDK packages include:
        - java.* (java.lang, java.util, java.io, etc.)
        - javax.* (javax.swing, javax.sql, etc.)
        - sun.* (internal, discouraged but sometimes used)
        - jdk.* (JDK 9+ modules)
    """
    from pants_backend_clojure.config import JDK_PACKAGE_PREFIXES

    return any(class_name.startswith(prefix) for prefix in JDK_PACKAGE_PREFIXES)
