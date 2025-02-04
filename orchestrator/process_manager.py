"""Process management functionality."""

import logging
import os
import subprocess
import time
from typing import Dict, List, Optional

import psutil

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
        self.processes: Dict[str, subprocess.Popen] = {}
        self.completed_files: List[str] = []
        self.failed_files: List[str] = []
        self.retry_counts: Dict[str, int] = {}
        self.max_retries = 3

        # Initialize with default thresholds
        self.resource_monitor = ResourceMonitor(
            thresholds={
                'cpu_percent': config.resources.cpu_percent,
                'memory_percent': config.resources.memory_percent,
                'disk_percent': config.resources.disk_percent,
                'max_processes': config.resources.max_processes
            },
            output_dir=self.config.directories.output_dir
        )

        # Calibrate resource usage if input files exist
        input_files = self._get_input_files()
        if input_files:
            self._calibrate_resource_usage(input_files[0])

    def _calibrate_resource_usage(self, test_file: str) -> None:
        """Run a test process to calibrate resource usage.

        Args:
            test_file: File to use for calibration
        """
        logger.info("Calibrating resource usage with test file: %s", test_file)

        # Start test process
        process = self.start_process(test_file)
        if not process:
            logger.error("Failed to start calibration process")
            return

        # Monitor process until resource usage stabilizes
        proc = psutil.Process(process.pid)
        last_cpu = 0
        stable_count = 0
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts:
            try:
                with proc.oneshot():
                    current_cpu = proc.cpu_percent()
                    if abs(current_cpu -
                           last_cpu) < 1.0:  # CPU usage change less than 1%
                        stable_count += 1
                        if stable_count >= 3:  # Stable for 3 consecutive checks
                            break
                    else:
                        stable_count = 0
                    last_cpu = current_cpu
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.error("Process ended before stabilizing")
                return
            attempt += 1

        # Get process resource usage
        try:
            proc = psutil.Process(process.pid)
            with proc.oneshot():
                cpu_percent = proc.cpu_percent(interval=1.0)
                memory_info = proc.memory_info()

            # Get system info
            cpu_count = psutil.cpu_count(
            ) or 1  # Default to 1 if CPU count not available
            total_memory = psutil.virtual_memory().total
            disk_usage = psutil.disk_usage(self.config.directories.output_dir)

            # Calculate max processes based on CPU (leave 20% headroom)
            max_processes_cpu = max(1, int(cpu_count * 0.8))

            # Calculate max processes based on memory
            memory_per_process = memory_info.rss
            if memory_per_process > 0:
                max_processes_memory = max(
                    1, int((total_memory * 0.8) / memory_per_process)
                )
            else:
                # If process uses negligible memory, default to CPU-based limit
                max_processes_memory = max_processes_cpu

            # Calculate max processes based on disk
            try:
                output_size = max(
                    1024,
                    os.path.getsize(test_file) * 2
                )  # Estimate output size, minimum 1KB
                max_processes_disk = max(
                    1, int((disk_usage.free * 0.8) / output_size)
                )
            except (OSError, IOError):
                # If file size can't be determined, default to CPU-based limit
                max_processes_disk = max_processes_cpu

            # Use the minimum of all constraints
            max_processes = min(
                max_processes_cpu, max_processes_memory, max_processes_disk
            )

            logger.info("Resource calibration results:")
            logger.info("  CPU usage per process: %.1f%%", cpu_percent)
            logger.info(
                "  Memory usage per process: %.1f MB",
                memory_info.rss / 1024 / 1024
            )
            logger.info(
                "  Estimated output size per process: %.1f MB",
                output_size / 1024 / 1024
            )
            logger.info("  System resources:")
            logger.info("    CPU cores: %d", cpu_count)
            logger.info(
                "    Total memory: %.1f GB", total_memory / 1024 / 1024 / 1024
            )
            logger.info(
                "    Free disk space: %.1f GB",
                disk_usage.free / 1024 / 1024 / 1024
            )
            logger.info("  Maximum processes:")
            logger.info("    Based on CPU: %d", max_processes_cpu)
            logger.info("    Based on memory: %d", max_processes_memory)
            logger.info("    Based on disk: %d", max_processes_disk)
            logger.info("  Final max processes: %d", max_processes)

            # Update resource monitor thresholds
            self.resource_monitor.thresholds.update({
                'cpu_percent': 80.0,  # Standard threshold
                'memory_percent': 80.0,  # Standard threshold
                'disk_percent': 80.0,  # Standard threshold
                'max_processes': max_processes
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error("Failed to calibrate resource usage: %s", e)

        # Clean up test process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        # Remove test file from tracking
        if test_file in self.processes:
            del self.processes[test_file]
        if test_file in self.resource_monitor.running_processes:
            self.resource_monitor.running_processes.remove(test_file)
        if test_file in self.completed_files:
            self.completed_files.remove(test_file)

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
            os.path.basename(input_file) + self.config.directories.output_suffix
        )

        # Build command with direct string substitution
        cmd = [self.config.binary.path]
        for flag in self.config.binary.flags:
            formatted_flag = flag.format(
                input_file=input_file, output_file=output_file
            )
            cmd.append(formatted_flag)

        logger.info("Built command: %s", ' '.join(cmd))
        return cmd

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
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                close_fds=True
            )
            self.processes[input_file] = process
            self.resource_monitor.running_processes.add(input_file)
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
            self.completed_files.append(input_file)
            return True

        logger.error(
            "Process failed for file %s with return code %d\nStdout:\n%s\nStderr:\n%s",
            input_file, return_code, stdout or "<no output>", stderr
            or "<no output>"
        )

        # Track retries
        self.retry_counts[input_file] = self.retry_counts.get(input_file, 0) + 1
        if self.retry_counts[input_file] >= self.max_retries:
            logger.error(
                "Max retries reached for file %s, marking as failed", input_file
            )
            self.failed_files.append(input_file)
            return False

        logger.info(
            "Retrying file %s (attempt %d/%d)", input_file,
            self.retry_counts[input_file], self.max_retries
        )
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
            while (current_index < total_files
                   and self.resource_monitor.can_start_new_process()):
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
