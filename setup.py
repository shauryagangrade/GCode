"""Packaging for GCode.

Build config lives in ``pyproject.toml``; this file exists for legacy
``python setup.py`` workflows.  Keep metadata in sync with
``pyproject.toml``.
"""

from setuptools import find_packages, setup

setup(
    name="gcode",
    version="0.2.0",
    description="GCode - a local, interactive AI coding CLI.",
    packages=find_packages(where="."),
    python_requires=">=3.10",
    install_requires=[
        "langchain>=1.3.14",
        "langchain-openai>=1.4.1",
        "langchain-core>=1.5.3",
        "python-dotenv>=1.2.2",
        "questionary>=2.1.1",
        "requests>=2.34.2",
        "rich>=15.0.0",
    ],
    entry_points={
        "console_scripts": [
            "gcode=gcode.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
