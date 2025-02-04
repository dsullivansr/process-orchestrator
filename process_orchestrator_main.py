#!/usr/bin/env python3
"""Main entry point for process orchestrator."""

import argparse
import logging
import os
import sys

from orchestrator.config import Config, OrchestratorOptions
from orchestrator.process_manager import ProcessManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Process files.')
    parser.add_argument(
        '--config', required=True, help='Path to configuration file'
    )
    parser.add_argument(
        '--input-file-list',
        required=False,
        help='Path to file containing list of input files (overrides config file)'
    )
    parser.add_argument(
        '--output-dir',
        required=False,
        help='Path to output directory (overrides config file)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level'
    )
    parser.add_argument(
        '--max-cpu-percent',
        type=float,
        default=80.0,
        help='Maximum CPU usage percentage'
    )
    parser.add_argument(
        '--max-memory-percent',
        type=float,
        default=80.0,
        help='Maximum memory usage percentage'
    )
    parser.add_argument(
        '--max-processes',
        type=int,
        default=4,
        help='Maximum number of concurrent processes'
    )
    return parser.parse_args()


def validate_config_file(config_path: str) -> None:
    """Validate config file exists.

    Args:
        config_path: Path to config file

    Raises:
        FileNotFoundError: If config file does not exist
    """
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    try:
        args = parse_args()
        validate_config_file(args.config)

        # Load base configuration
        config = Config.from_yaml(args.config)

        # Combine and validate options from args and config
        try:
            options = OrchestratorOptions.from_args_and_config(args, config)
        except (ValueError, FileNotFoundError) as e:
            logger.error(str(e))
            return 1

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, options.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger.info("Output directory: %s", options.output_dir)

        # Update config with combined options
        config.directories.input_file_list = options.input_file_list
        config.directories.output_dir = options.output_dir
        config.resources.cpu_percent = options.max_cpu_percent
        config.resources.memory_percent = options.max_memory_percent
        config.resources.max_processes = options.max_processes

        # Initialize process manager
        manager = ProcessManager(config)

        # Start processing
        return manager.run()

    except Exception as e:
        logger.error("Error: %s", e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
