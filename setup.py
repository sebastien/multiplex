#!/usr/bin/env python3
import sys
from setuptools import setup
from pathlib import Path

if sys.version_info < (3, 8):
	sys.exit("Error: multiplex requires Python 3.8 or later")

README_PATH = Path(__file__).parent / "README.md"
with open(README_PATH, "r", encoding="utf-8") as f:
	long_description = f.read()

VERSION = "1.0.0"
REQUIREMENTS = []
EXTRAS_REQUIRE = {
	"dev": [
		"pytest>=6.0",
		"black>=22.0",
		"flake8>=4.0",
		"mypy>=0.950",
	],
	"test": [
		"pytest>=6.0",
		"pytest-cov>=2.0",
	],
}

# Classifiers for PyPI
CLASSIFIERS = [
	"Development Status :: 5 - Production/Stable",
	"Environment :: Console",
	"Intended Audience :: Developers",
	"Intended Audience :: System Administrators",
	"License :: OSI Approved :: BSD License",
	"Operating System :: MacOS",
	"Operating System :: POSIX",
	"Operating System :: Unix",
	"Programming Language :: Python :: 3",
	"Programming Language :: Python :: 3.8",
	"Programming Language :: Python :: 3.9",
	"Programming Language :: Python :: 3.10",
	"Programming Language :: Python :: 3.11",
	"Programming Language :: Python :: 3.12",
	"Programming Language :: Python :: 3.13",
	"Programming Language :: Python :: 3 :: Only",
	"Topic :: Software Development :: Build Tools",
	"Topic :: System :: Systems Administration",
	"Topic :: Utilities",
	"Topic :: System :: Shells",
	"Topic :: System :: System Shells",
	"Topic :: Software Development :: Testing",
]

# Keywords for PyPI search
KEYWORDS = [
	"multiplex",
	"process",
	"command",
	"parallel",
	"concurrent",
	"shell",
	"cli",
	"automation",
	"build",
	"coordination",
	"orchestration",
]

setup(
	name="multiplex-sh",
	version=VERSION,
	description="A command-line multiplexer for running multiple processes in parallel with coordination",
	long_description=long_description,
	long_description_content_type="text/markdown",
	author="Sébastien Pierre",
	author_email="sebastien@ffctn.com",
	url="https://github.com/sebastien/multiplex",
	project_urls={
		"Bug Reports": "https://github.com/sebastien/multiplex/issues",
		"Source": "https://github.com/sebastien/multiplex",
		"Documentation": "https://github.com/sebastien/multiplex#readme",
	},
	license="BSD-3-Clause",
	classifiers=CLASSIFIERS,
	keywords=" ".join(KEYWORDS),
	# Package discovery
	packages=[],  # No packages, just a single module
	package_dir={"": "src/py"},
	py_modules=["multiplex"],
	# Package data
	package_data={
		"": ["README.md", "LICENSE", "examples/*.sh"],
	},
	include_package_data=True,
	# Dependencies
	python_requires=">=3.12",
	install_requires=REQUIREMENTS,
	extras_require=EXTRAS_REQUIRE,
	# Entry points for command-line usage
	entry_points={
		"console_scripts": [
			"multiplex=multiplex:cli",
		],
	},
	# Additional metadata for PyPI
	zip_safe=False,  # For better compatibility
	platforms=["unix", "linux", "osx"],
	# Test configuration
	test_suite="tests",
	tests_require=EXTRAS_REQUIRE["test"],
	# Additional files to include
	data_files=[
		(
			"share/multiplex/examples",
			[
				"examples/actions-demo.sh",
				"examples/cicd-pipeline.sh",
				"examples/complete-demo.sh",
				"examples/dev-environment.sh",
				"examples/http-benchmark.sh",
				"examples/parallel-coordination.sh",
				"examples/process-delays.sh",
				"examples/sequential-build.sh",
				"examples/special-cases.sh",
				"examples/time-delays.sh",
				"examples/README.md",
			],
		),
		("share/doc/multiplex", ["README.md", "LICENSE"]),
	],
)
