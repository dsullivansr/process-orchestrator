#!/usr/bin/env python3
"""Main entry point for process orchestrator."""

import argparse
import logging
import os
import sys
from typing import Dict

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Process files.')
    parser.add_argument('--config',
                        required=True,
                        help='Path to configuration file')
    parser.add_argument('--input-file-list',
                        required=True,
                        help='Path to file containing list of input files')
    parser.add_argument('--output-dir',
                        required=True,
                        help='Path to output directory')
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level')
    parser.add_argument('--max-cpu-percent',
                        type=float,
                        default=80.0,
                        help='Maximum CPU usage percentage')
    parser.add_argument('--max-memory-percent',
                        type=float,
                        default=80.0,
                        help='Maximum memory usage percentage')
    parser.add_argument('--max-processes',
                        type=int,
                        default=4,
                        help='Maximum number of concurrent processes')
    return parser.parse_args()


def validate_paths(args: argparse.Namespace) -> None:
    """Validate input paths.

    Args:
        args: Command line arguments

    Raises:
        FileNotFoundError: If input file list or config file does not exist
    """
    if not os.path.isfile(args.config):
        raise FileNotFoundError(f"Config file not found: {args.config}")

    if not os.path.isfile(args.input_file_list):
        raise FileNotFoundError(
            f"Input file list not found: {args.input_file_list}")

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    logger.info("Output directory: %s", args.output_dir)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    try:
        args = parse_args()
        validate_paths(args)

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Load base configuration
        config = Config.from_yaml(args.config)

        # Update directories with CLI arguments
        config.directories.input_file_list = args.input_file_list
        config.directories.output_dir = args.output_dir

        # Set resource thresholds
        thresholds: Dict[str, float] = {
            'cpu_percent': args.max_cpu_percent,
            'memory_percent': args.max_memory_percent,
            'disk_percent': 90.0  # Default disk threshold
        }

        # Initialize process manager
        manager = ProcessManager(config, thresholds=thresholds)

        # Start processing
        return manager.run()

    except Exception as e:
        logger.error("Error: %s", e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
