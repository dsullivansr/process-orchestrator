"""Configuration management for the orchestrator."""

import os
from dataclasses import dataclass
from typing import List

import yaml


@dataclass
class BinaryConfig:
    """Configuration for the binary to execute."""
    path: str
    flags: List[str]


@dataclass
class DirectoryConfig:
    """Configuration for input and output directories."""
    input_dir: str
    output_dir: str


class Config:
    """Configuration for the process orchestrator."""

    def __init__(self, config_path: str = None, **kwargs):
        """Initialize configuration.

        Args:
            config_path: Path to YAML configuration file.
            **kwargs: Override configuration with keyword arguments.
        """
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        else:
            config = {}

        # Allow kwargs to override file configuration
        config.update(kwargs)

        # Initialize binary configuration
        binary_config = config.get('binary', {})
        if isinstance(binary_config, BinaryConfig):
            self.binary = binary_config
        else:
            self.binary = BinaryConfig(path=binary_config.get(
                'path', '/usr/bin/test'),
                                       flags=binary_config.get('flags', []))

        # Initialize directory configuration
        directory_config = config.get('directories', {})
        if isinstance(directory_config, DirectoryConfig):
            self.directories = directory_config
        else:
            self.directories = DirectoryConfig(
                input_dir=directory_config.get('input_dir', '/tmp/input'),
                output_dir=directory_config.get('output_dir', '/tmp/output'))
