"""Configuration classes for process orchestration."""

import os
from dataclasses import dataclass
from typing import List, Optional

import yaml


@dataclass
class BinaryConfig:
    """Binary configuration."""
    path: Optional[str] = None
    flags: List[str] = None

    def __post_init__(self):
        """Validate binary configuration."""
        if not self.path:
            raise ValueError("Binary path cannot be empty")
        if self.flags is None:
            self.flags = []

    def build_command(self,
                      input_file: str,
                      output_file: Optional[str] = None) -> List[str]:
        """Build command for execution.

        Args:
            input_file: Input file path
            output_file: Optional output file path

        Returns:
            List of command parts
        """
        command = [self.path]
        for flag in self.flags:
            if '{input_file}' in flag:
                flag = flag.replace('{input_file}', input_file)
            if output_file is not None and '{output_file}' in flag:
                flag = flag.replace('{output_file}', output_file)
            command.append(flag)
        return command


@dataclass
class DirectoryConfig:
    """Directory configuration."""
    input_file_list: Optional[str] = None
    output_dir: Optional[str] = None
    output_suffix: str = ""

    def __post_init__(self):
        """Validate directory configuration."""
        if not self.input_file_list:
            raise ValueError("Input file list cannot be empty")
        if not os.path.isfile(self.input_file_list):
            raise FileNotFoundError(
                f"Input file list not found: {self.input_file_list}"
            )
        if not self.output_dir:
            raise ValueError("Output directory cannot be empty")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Convert None to empty string for easier comparison
        if self.output_suffix is None:
            self.output_suffix = ""


@dataclass
class ResourceConfig:
    """Resource threshold configuration."""
    cpu_percent: float = 80.0
    memory_percent: float = 80.0
    disk_percent: float = 90.0
    max_processes: int = 2

    def __post_init__(self):
        """Validate resource configuration."""
        if not 0 <= self.cpu_percent <= 100:
            raise ValueError("CPU percent must be between 0 and 100")
        if not 0 <= self.memory_percent <= 100:
            raise ValueError("Memory percent must be between 0 and 100")
        if not 0 <= self.disk_percent <= 100:
            raise ValueError("Disk percent must be between 0 and 100")
        if self.max_processes < 1:
            raise ValueError("Max processes must be at least 1")


@dataclass
class OrchestratorOptions:
    """Combined options from command line and config file."""
    input_file_list: str
    output_dir: str
    log_level: str = 'INFO'
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 80.0
    max_processes: int = 2

    def __post_init__(self):
        """Validate options."""
        if not self.input_file_list:
            raise ValueError('Input file list must be provided')
        if not self.output_dir:
            raise ValueError('Output directory must be provided')
        if not os.path.isfile(self.input_file_list):
            raise FileNotFoundError(
                f'Input file list not found: {self.input_file_list}'
            )
        os.makedirs(self.output_dir, exist_ok=True)

    @classmethod
    def from_args_and_config(
        cls, args: 'argparse.Namespace', config: 'Config'
    ) -> 'OrchestratorOptions':
        """Create options from command line args and config file.

        Args:
            args: Command line arguments
            config: Config from YAML file

        Returns:
            Combined options
        """
        return cls(
            input_file_list=args.input_file_list
            or config.directories.input_file_list,
            output_dir=args.output_dir or config.directories.output_dir,
            log_level=args.log_level,
            max_cpu_percent=args.max_cpu_percent,
            max_memory_percent=args.max_memory_percent,
            max_processes=args.max_processes
        )


@dataclass
class Config:
    """Configuration for process orchestration."""
    binary: BinaryConfig
    directories: DirectoryConfig

    def __init__(self, **kwargs):
        """Initialize configuration.

        Args:
            **kwargs: Configuration parameters including 'binary', 'directories', and 'resources'

        Raises:
            ValueError: If configuration is invalid
            TypeError: If configuration type is invalid
        """
        # Handle binary config
        binary = kwargs.get('binary', {})
        if isinstance(binary, dict):
            self.binary = BinaryConfig(**binary)
        elif isinstance(binary, BinaryConfig):
            self.binary = binary
        else:
            raise TypeError(
                "Binary configuration must be a dict or BinaryConfig"
            )

        # Handle directory config
        directories = kwargs.get('directories', {})
        if isinstance(directories, dict):
            self.directories = DirectoryConfig(**directories)
        elif isinstance(directories, DirectoryConfig):
            self.directories = directories
        else:
            raise TypeError(
                "Directory configuration must be a dict or DirectoryConfig"
            )

        # Handle resource config
        resources = kwargs.get('resources', {})
        if isinstance(resources, dict):
            self.resources = ResourceConfig(**resources)
        elif isinstance(resources, ResourceConfig):
            self.resources = resources
        else:
            self.resources = ResourceConfig()

    @classmethod
    def from_yaml(cls, config_path: str) -> 'Config':
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Config object

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If config file is invalid
        """
        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)
