PLUGIN_VERSION = "0.1.0"

pants_requirements(name="pants", resolve="pants-plugins")

python_requirements(name="pants-reqs", resolve="pants-plugins", source="requirements.txt")

python_requirements(name="pants-test-reqs", resolve="pants-plugins", source="test-requirements.txt")

python_sources(name="pants-plugin-sources", resolve="pants-plugins", sources=["pants_backend_clojure/**/*.py"], dependencies=[":pants", ":pants-reqs"])

python_sources(name="test-fixtures", resolve="pants-plugins", sources=["tests/**/clojure_test_fixtures.py"])

python_tests(name="test-plugin-sources", resolve="pants-plugins", sources=["tests/**/test_*.py"], dependencies=[":pants-reqs", ":pants-test-reqs", ":pants-plugin-sources", ":test-fixtures"])

python_distribution(
    name="wheel",
    dependencies=[
        ":pants-plugin-sources",
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