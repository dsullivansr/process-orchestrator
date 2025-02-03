"""Configuration management for process orchestration."""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict

import yaml


@dataclass
class BinaryConfig:
    """Configuration for binary execution."""
    path: str
    flags: List[str]

    def __post_init__(self):
        """Validate binary configuration."""
        if not self.path:
            raise ValueError("Binary path cannot be empty")
        if not self.flags:
            raise ValueError("Binary flags cannot be empty")


@dataclass
class DirectoryConfig:
    """Configuration for input/output directories."""
    input_dir: str
    output_dir: str
    output_suffix: Optional[str] = field(default='')

    def __post_init__(self):
        """Validate directory configuration."""
        if not self.input_dir:
            raise ValueError("Input directory cannot be empty")
        if not self.output_dir:
            raise ValueError("Output directory cannot be empty")

        # Convert None to empty string for easier comparison
        if self.output_suffix is None:
            self.output_suffix = ""

        # Normalize paths for comparison
        input_dir = os.path.abspath(self.input_dir)
        output_dir = os.path.abspath(self.output_dir)

        # If input and output directories are the same, output_suffix is required
        if input_dir == output_dir and not self.output_suffix:
            raise ValueError(
                "Output suffix is required when input and output directories are the same"
            )


@dataclass
class Config:
    """Configuration for process orchestration."""
    binary: BinaryConfig
    directories: DirectoryConfig

    def __init__(self, binary: Union[Dict, BinaryConfig],
                 directories: Union[Dict, DirectoryConfig]):
        """Initialize configuration.

        Args:
            binary: Binary configuration dictionary or BinaryConfig object
            directories: Directory configuration dictionary or DirectoryConfig object

        Raises:
            ValueError: If configuration is invalid
        """
        # Handle binary config
        if isinstance(binary, dict):
            self.binary = BinaryConfig(path=binary.get('path'),
                                       flags=binary.get('flags', []))
        elif isinstance(binary, BinaryConfig):
            self.binary = binary
        else:
            raise TypeError(
                "Binary configuration must be a dict or BinaryConfig")

        # Handle directory config
        if isinstance(directories, dict):
            self.directories = DirectoryConfig(
                input_dir=directories.get('input_dir'),
                output_dir=directories.get('output_dir'),
                output_suffix=directories.get('output_suffix', ''))
        elif isinstance(directories, DirectoryConfig):
            self.directories = directories
        else:
            raise TypeError(
                "Directory configuration must be a dict or DirectoryConfig")

    @classmethod
    def load_from_file(cls, config_file: str) -> 'Config':
        """Load configuration from YAML file.

        Args:
            config_file: Path to YAML configuration file

        Returns:
            Config object

        Raises:
            FileNotFoundError: If configuration file does not exist
            yaml.YAMLError: If configuration file is invalid YAML
            ValueError: If configuration is invalid
        """
        if not os.path.exists(config_file):
            raise FileNotFoundError(
                f"Configuration file not found: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)
