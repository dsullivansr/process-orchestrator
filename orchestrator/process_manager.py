"""Process management functionality."""

import logging
import os
import subprocess
import time
from typing import Dict, List, Optional

from orchestrator.config import Config
from orchestrator.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)


class ProcessManager:
    """Process manager for orchestrating file processing."""

    def __init__(self, config: Config) -> None:
        """Initialize process manager.

        Args:
            config: Configuration object
        """
        self.config = config
        self.resource_monitor = ResourceMonitor(
            thresholds={
                'cpu_percent': config.resources.cpu_percent,
                'memory_percent': config.resources.memory_percent,
                'disk_percent': config.resources.disk_percent,
                'max_processes': config.resources.max_processes
            },
            output_dir=self.config.directories.output_dir)
        self.processes: Dict[str, subprocess.Popen] = {}
        self.completed_files: List[str] = []
        self.failed_files: List[str] = []
        self.retry_counts: Dict[str, int] = {}
        self.max_retries = 3

    def build_command(self, input_file: str) -> List[str]:
        """Build command for processing a file.

        Args:
            input_file: Input file path

        Returns:
            Command list
        """
        # Get output path with suffix
        output_file = os.path.join(
            self.config.directories.output_dir,
            os.path.basename(input_file) +
            self.config.directories.output_suffix)

        # Build command with direct string substitution
        cmd = [self.config.binary.path]
        for flag in self.config.binary.flags:
            formatted_flag = flag.format(input_file=input_file,
                                         output_file=output_file)
            cmd.append(formatted_flag)

        logger.info("Built command: %s", ' '.join(cmd))
        return cmd

    def _get_input_files(self) -> List[str]:
        """Get list of input files.

        Returns:
            List of input file paths
        """
        with open(self.config.directories.input_file_list,
                  'r',
                  encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def start_process(self, input_file: str) -> Optional[subprocess.Popen]:
        """Start a new process.

        Args:
            input_file: Input file path

        Returns:
            Process object if started successfully, None otherwise

        Raises:
            FileNotFoundError: If input file does not exist
        """
        # Check if file is already being processed or has been processed
        if input_file in self.processes:
            logger.warning("File %s is already being processed", input_file)
            return None
        if input_file in self.completed_files:
            logger.warning("File %s has already been processed", input_file)
            return None
        if input_file in self.failed_files:
            logger.warning("File %s has already failed", input_file)
            return None

        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Build command
        cmd = self.build_command(input_file)

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(cmd[-1])
        os.makedirs(output_dir, exist_ok=True)

        # Start process
        logger.info("Starting process for file: %s", input_file)
        logger.info("Command: %s", ' '.join(cmd))

        try:
            # pylint: disable=consider-using-with
            process = subprocess.Popen(cmd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       text=True,
                                       bufsize=1,
                                       close_fds=True)
            self.processes[input_file] = process
            self.resource_monitor.running_processes.add(input_file)
            return process
        except Exception as e:
            logger.error("Failed to start process for file %s: %s", input_file,
                         e)
            self.failed_files.append(input_file)
            return None

    def _check_process(self, input_file: str,
                       process: subprocess.Popen) -> Optional[bool]:
        """Check process status.

        Args:
            input_file: Input file path
            process: Process object

        Returns:
            True if process completed successfully, False if failed,
            None if still running
        """
        return_code = process.poll()

        if return_code is None:
            return None

        # Process finished
        stdout, stderr = process.communicate()

        if return_code == 0:
            logger.info("Process completed successfully for file: %s",
                        input_file)
            self.completed_files.append(input_file)
            return True

        logger.error(
            "Process failed for file %s with return code %d\nStdout:\n%s\nStderr:\n%s",
            input_file, return_code, stdout or "<no output>", stderr or
            "<no output>")

        # Track retries
        self.retry_counts[input_file] = self.retry_counts.get(input_file, 0) + 1
        if self.retry_counts[input_file] >= self.max_retries:
            logger.error("Max retries reached for file %s, marking as failed",
                         input_file)
            self.failed_files.append(input_file)
            return False

        logger.info("Retrying file %s (attempt %d/%d)", input_file,
                    self.retry_counts[input_file], self.max_retries)
        return None  # Keep the process in the queue for retry

    def _check_processes(self) -> None:
        """Check status of all running processes."""
        finished = []
        for input_file, process in self.processes.items():
            result = self._check_process(input_file, process)
            if result is not None:  # Process finished (success or failure)
                finished.append(input_file)

        # Remove finished processes (both completed and failed)
        for input_file in finished:
            del self.processes[input_file]
            self.resource_monitor.running_processes.remove(input_file)

    def run(self) -> int:
        """Run process manager.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        input_files = self._get_input_files()
        total_files = len(input_files)
        current_index = 0

        logger.info("Starting process manager with %d files", total_files)

        while (current_index < total_files or self.processes):
            # Check running processes
            self._check_processes()

            # Start new processes if resources available
            while (current_index < total_files and
                   self.resource_monitor.can_start_new_process()):
                input_file = input_files[current_index]
                if input_file not in self.processes and \
                   input_file not in self.completed_files and \
                   input_file not in self.failed_files and \
                   input_file not in self.resource_monitor.running_processes:
                    process = self.start_process(input_file)
                    if process:
                        current_index += 1
                    else:
                        # If start_process failed, skip this file
                        current_index += 1
                else:
                    current_index += 1

            # Sleep briefly to avoid busy waiting
            if self.processes:
                time.sleep(0.1)

        # Log final status
        logger.info("Process manager finished")
        logger.info("Completed files: %d", len(self.completed_files))
        logger.info("Failed files: %d", len(self.failed_files))

        # Return non-zero exit code if any files failed
        return 1 if self.failed_files else 0
