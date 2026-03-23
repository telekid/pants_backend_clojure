from __future__ import annotations

import pytest
from pants_backend_clojure.goals.test import extract_test_namespace


@pytest.mark.parametrize(
    "description, content, expected",
    [
        (
            "simple namespace",
            "(ns example.core)",
            "example.core",
        ),
        (
            "map metadata (single line)",
            '(ns ^{:doc "Desc"} my.ns)',
            "my.ns",
        ),
        (
            "keyword metadata",
            "(ns ^:no-doc my.ns)",
            "my.ns",
        ),
        (
            "multiple metadata",
            '(ns ^:no-doc ^{:added "1.0"} my.ns)',
            "my.ns",
        ),
        (
            "map then keyword metadata",
            '(ns ^{:doc "abc"} ^:no-doc my.ns)',
            "my.ns",
        ),
        (
            "multiline with map metadata",
            '(ns ^{:doc "Desc"}\n  my.ns)',
            "my.ns",
        ),
        (
            "multiline with keyword metadata",
            "(ns ^:no-doc\n  my.ns)",
            "my.ns",
        ),
        (
            "hyphens in namespace",
            "(ns my-project.core-test)",
            "my-project.core-test",
        ),
        (
            "underscores in namespace",
            "(ns my_project.core)",
            "my_project.core",
        ),
        (
            "with require clause",
            "(ns example.core\n  (:require [clojure.test]))",
            "example.core",
        ),
        (
            "no namespace form",
            "(defn foo [] 1)",
            None,
        ),
        (
            "empty string",
            "",
            None,
        ),
        (
            "comment before ns",
            "; comment\n(ns my.ns)",
            "my.ns",
        ),
        (
            "type hint metadata",
            "(ns ^String my.ns)",
            "my.ns",
        ),
        (
            "real-world Pedestal pattern",
            '(ns ^{:doc "Integration tests..."}\n  io.pedestal.http.cors-test\n  (:require [clojure.test]))',
            "io.pedestal.http.cors-test",
        ),
    ],
    ids=lambda x: x if isinstance(x, str) and " " in x else "",
)
def test_extract_test_namespace(description: str, content: str, expected: str | None) -> None:
    assert extract_test_namespace(content) == expected
