"""Process management functionality."""

import logging
import os
import subprocess
from typing import Dict, List, Optional, Tuple

import psutil

from orchestrator.config import Config
from orchestrator.resource_monitor import ResourceMonitor
from orchestrator.resource_calibration import ResourceCalibrator, NoopCalibrator, ProcessCalibrator

logger = logging.getLogger(__name__)


class ProcessManager:
    """Process manager for orchestrating file processing."""

    def __init__(
        self,
        config: Config,
        *,
        calibrator: Optional[ResourceCalibrator] = None,
        skip_calibration: bool = False
    ) -> None:
        """Initialize process manager.

        Args:
            config: Configuration object
            calibrator: Optional resource calibrator. If None, uses NoopCalibrator.
            skip_calibration: Whether to skip resource calibration
        """
        self.config = config
        self.processes: Dict[str, subprocess.Popen] = {}
        self.completed_files: List[str] = []
        self.failed_files: List[str] = []
        self.retry_counts: Dict[str, int] = {}
        self.max_retries = 3

        # Initialize with default thresholds
        thresholds = {
            'cpu_percent': config.resources.cpu_percent,
            'memory_percent': config.resources.memory_percent,
            'disk_percent': config.resources.disk_percent,
            'max_processes': config.resources.max_processes
        }

        # Calibrate resource usage if not skipped and input files exist
        self.calibrator = calibrator or (
            NoopCalibrator() if skip_calibration else ProcessCalibrator(config)
        )
        input_files = self._get_input_files()
        if input_files and not skip_calibration:
            calibrated = self.calibrator.calibrate(input_files[0])
            if calibrated:
                thresholds.update(calibrated)

        self.resource_monitor = ResourceMonitor(
            thresholds=thresholds,
            output_dir=self.config.directories.output_dir
        )

    def build_command(self, input_file: str) -> Tuple[object, bool]:
        """Build command for processing a file with proper substitution and shell redirection handling.

        Args:
            input_file: Input file path

        Returns:
            A tuple of (command, use_shell) where command is either a list or a string, and use_shell indicates whether shell=True should be used.
        """
        # Get output path with suffix
        output_file = os.path.join(
            self.config.directories.output_dir,
            os.path.basename(input_file) + self.config.directories.output_suffix
        )

        # Format flags with substitution
        formatted_flags = [
            flag.format(input_file=input_file, output_file=output_file)
            for flag in self.config.binary.flags
        ]

        # Check if any flag contains shell operators that require shell interpretation
        if any(op in formatted_flags for op in [">", ">>", "|", "<"]):
            # Build a command string for shell execution
            cmd_str = self.config.binary.path + " " + " ".join(formatted_flags)
            logger.info("Built shell command: %s", cmd_str)
            return cmd_str, True
        cmd_list = [self.config.binary.path] + formatted_flags
        logger.info("Built command: %s", ' '.join(cmd_list))
        return cmd_list, False

    def _get_input_files(self) -> List[str]:
        """Get list of input files.

        Returns:
            List of input file paths
        """
        with open(self.config.directories.input_file_list, 'r',
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

        # Build command and determine if shell should be used
        cmd, use_shell = self.build_command(input_file)

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(cmd[-1] if isinstance(cmd, list) else cmd)
        os.makedirs(output_dir, exist_ok=True)

        # Start process
        logger.info("Starting process for file: %s", input_file)
        logger.info(
            "Command: %s", ' '.join(cmd) if isinstance(cmd, list) else cmd
        )

        try:
            # pylint: disable=consider-using-with
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                close_fds=True,
                shell=use_shell
            )
            self.processes[input_file] = process
            self.resource_monitor.add_process(
                input_file, psutil.Process(process.pid)
            )
            return process
        except Exception as e:
            logger.error(
                "Failed to start process for file %s: %s", input_file, e
            )
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
            logger.info(
                "Process completed successfully for file: %s", input_file
            )
            # Process completed successfully
            self.completed_files.append(input_file)
            return True

        logger.error(
            "Process failed for file %s with return code %d\nStdout:\n%s\nStderr:\n%s",
            input_file, return_code, stdout or "<no output>", stderr
            or "<no output>"
        )

        # Track retries
        if input_file not in self.retry_counts:
            self.retry_counts[input_file] = 0

        # Log retry attempt
        logger.info(
            "Process failed for file %s (attempt %d/%d)", input_file,
            self.retry_counts[input_file] + 1, self.max_retries
        )

        # Increment retry count after logging
        self.retry_counts[input_file] += 1

        if self.retry_counts[input_file] >= self.max_retries:
            logger.error(
                "Max retries reached for file %s, marking as failed", input_file
            )
            self.failed_files.append(input_file)
            return False

        # Process failed but can be retried
        return None  # Keep the process in the queue for retry

    def _check_processes(self) -> None:
        """Check status of all running processes."""
        # Get a list of current processes to avoid modifying during iteration
        current_processes = list(self.processes.items())
        finished = []
        needs_retry = []

        # Check each process
        for input_file, process in current_processes:
            result = self._check_process(input_file, process)
            if result is True:
                # Process completed successfully
                finished.append(input_file)
            elif result is False:
                # Process failed and hit max retries
                finished.append(input_file)
            elif result is None and input_file not in self.completed_files:
                # Process still running
                continue

            # Clean up process if it's done
            if input_file in self.processes:
                del self.processes[input_file]
                self.resource_monitor.remove_process(input_file)

            # Add to retry list if needed
            if result is False and self.retry_counts[input_file
                                                     ] < self.max_retries:
                needs_retry.append(input_file)

        # Retry failed processes that haven't hit max retries
        for input_file in needs_retry:
            if input_file not in self.failed_files:
                process = self.start_process(input_file)
                if process:
                    self.processes[input_file] = process

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
            while (current_index < total_files
                   and self.resource_monitor.can_start_new_process()):
                input_file = input_files[current_index]
                # Skip if file is already being processed or has been processed
                if input_file in self.processes:
                    current_index += 1
                    continue

                if input_file in self.completed_files or input_file in self.failed_files:
                    current_index += 1
                    continue

                # Initialize retry count if not already set
                if input_file not in self.retry_counts:
                    self.retry_counts[input_file] = 0

                process = self.start_process(input_file)
                if process:
                    self.processes[input_file] = process
                    current_index += 1
                elif self.retry_counts[input_file] >= self.max_retries:
                    # If we've hit max retries, mark as failed and move on
                    self.failed_files.append(input_file)
                    current_index += 1

            # If no processes are running and we can't start new ones, we're done
            if not self.processes and (
                    current_index >= total_files
                    or not self.resource_monitor.can_start_new_process()):
                break

        # Log final status
        logger.info("Process manager finished")
        logger.info("Completed files: %d", len(self.completed_files))
        logger.info("Failed files: %d", len(self.failed_files))

        # Return non-zero exit code if any files failed or not all files were processed
        total_files = len(input_files)
        if len(self.failed_files) > 0:
            logger.error("Some files failed processing")
            return 1
        if len(self.completed_files) < total_files:
            logger.error("Not all files were processed")
            return 1
        return 0
