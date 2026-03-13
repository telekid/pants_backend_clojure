PLUGIN_VERSION = "0.1.1"

pants_requirements(name="pants", resolve="pants-plugins")

python_requirements(name="pants-reqs", resolve="pants-plugins", source="requirements.txt")

python_requirements(name="pants-test-reqs", resolve="pants-plugins", source="test-requirements.txt")

python_sources(name="pants-plugin-sources", resolve="pants-plugins", sources=["pants_backend_clojure/**/*.py"], dependencies=[":pants", ":pants-reqs"])

python_sources(name="test-fixtures", resolve="pants-plugins", sources=["tests/**/clojure_test_fixtures.py"])

python_tests(name="test-plugin-sources", resolve="pants-plugins", sources=["tests/**/test_*.py"], dependencies=[":pants-reqs", ":pants-test-reqs", ":pants-plugin-sources", ":test-fixtures"])

# The !! (strong exclude) dependencies below prevent pantsbuild.pants and
# pantsbuild.pants.testutil from appearing in the wheel's install_requires.
# Pants supplies these at runtime from its own venv, so they must not be
# declared as dependencies of the published plugin. Without these excludes,
# the pants_requirements generator target (:pants) pulls both packages into
# the dependency graph, and pantsbuild.pants.testutil doesn't even exist on
# PyPI for Pants >= 2.18.
#
# Other approaches we considered:
#   - Depending on ":pants#pantsbuild.pants" instead of ":pants" in
#     pants-plugin-sources. This avoids testutil but still puts
#     pantsbuild.pants in install_requires, which is unnecessary.
#   - Setting testutil=False on pants_requirements. This prevents the
#     testutil target from being generated at all, which would break tests
#     that import from pants.testutil.
#   - Removing the explicit :pants dependency entirely and relying on
#     inference. This works but is fragile and less explicit.
python_distribution(
    name="wheel",
    dependencies=[
        ":pants-plugin-sources",
        "!!:pants#pantsbuild.pants",
        "!!:pants#pantsbuild.pants.testutil",
    ],
    provides=setup_py(
        name="pants-backend-clojure",
        version=PLUGIN_VERSION,
        description="A Clojure backend for the Pants build system",
        author="Stephen Hopper",
        author_email="stephenmhopper@gmail.com",
        url="https://github.com/enragedginger/pants_backend_clojure",
        license="Apache-2.0",
        python_requires=">=3.11",
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.11",
            "Topic :: Software Development :: Build Tools",
        ],
        keywords=["pantsbuild", "pants", "clojure", "jvm", "build-system"],
        long_description_content_type="text/markdown",
    ),
    long_description_path="README.md",
    wheel=True,
    sdist=True,
)