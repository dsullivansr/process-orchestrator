"""Setup script for the process orchestrator."""

from setuptools import setup, find_packages

setup(
    name="process-orchestrator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "psutil>=5.9.0",
        "pyyaml>=6.0.1",
    ],
    python_requires=">=3.8",
)
