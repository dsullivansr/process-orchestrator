"""Resource calibration functionality."""

from abc import ABC, abstractmethod
import logging
import os
import subprocess
import time
from typing import Dict, Optional

import psutil

from orchestrator.config import Config

logger = logging.getLogger(__name__)


class ResourceCalibrator(ABC):
    """Interface for resource calibration."""

    @abstractmethod
    def calibrate(self, test_file: str) -> Optional[Dict[str, float]]:
        """Run calibration on a test file.

        Args:
            test_file: File to use for calibration

        Returns:
            Optional dictionary of calibrated thresholds. If None, use defaults.
        """
        return None


class NoopCalibrator(ResourceCalibrator):
    """Calibrator that does no calibration."""

    def calibrate(self, test_file: str) -> Optional[Dict[str, float]]:
        """Run calibration on a test file.

        Args:
            test_file: File to use for calibration

        Returns:
            None since this calibrator performs no calibration.
        """
        return None


class ProcessCalibrator(ResourceCalibrator):
    """Calibrator that measures resource usage of test processes."""

    def __init__(self, config: Config, skip_calibration: bool = False) -> None:
        """Initialize calibrator.

        Args:
            config: Configuration object
            skip_calibration: Whether to skip calibration and use default thresholds
        """
        self.config = config
        self.skip_calibration = skip_calibration

    def start_process(self, input_file: str) -> Optional[subprocess.Popen]:
        """Start a calibration process.

        Args:
            input_file: Input file path

        Returns:
            Process object if started successfully, None otherwise
        """
        if not input_file or not os.path.exists(input_file):
            logger.error("Input file does not exist: %s", input_file)
            return None

        try:
            command = self.config.binary.build_command(input_file)
            with subprocess.Popen(command, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) as process:
                # Keep process open for calibration
                process.poll()
                return process
        except (subprocess.SubprocessError, OSError) as e:
            logger.error("Failed to start process: %s", e)
            return None

    def calibrate(self, test_file: str) -> Optional[Dict[str, float]]:
        """Run calibration on a test file.

        Args:
            test_file: File to use for calibration

        Returns:
            Dictionary of calibrated thresholds
        """
        logger.info("Calibrating resource usage with test file: %s", test_file)

        # Start test process
        process = self.start_process(test_file)
        if not process:
            logger.error("Failed to start calibration process")
            return None

        # Give the process a moment to start
        time.sleep(0.1)

        # Monitor process until resource usage stabilizes
        try:
            proc = psutil.Process(process.pid)
        except psutil.NoSuchProcess:
            logger.error("Process terminated before monitoring could start")
            return None

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
                return None
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

            # Calculate max processes based on memory (leave 20% headroom)
            process_memory = max(memory_info.rss, 1024)  # Minimum 1KB
            max_processes_memory = max(
                1, int((total_memory * 0.8) / process_memory)
            )

            # Calculate max processes based on disk space (leave 20% headroom)
            output_size = os.path.getsize(test_file)
            available_space = disk_usage.free
            max_processes_disk = max(
                1, int((available_space * 0.8) / output_size)
            )

            # Use minimum of CPU, memory and disk constraints
            max_processes = min(
                max_processes_cpu, max_processes_memory, max_processes_disk
            )

            # Set thresholds based on calibration
            return {
                'cpu_percent': max(1.0, cpu_percent) *
                               1.2,  # Add 20% headroom, minimum 1% CPU
                'memory_percent': (process_memory / total_memory) * 100 * 1.2,
                'disk_percent': (output_size / available_space) * 100 * 1.2,
                'max_processes': max_processes
            }

        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as e:
            logger.error("Failed to get resource usage: %s", e)
            return None
        finally:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Failed to terminate calibration process: %s", e)
