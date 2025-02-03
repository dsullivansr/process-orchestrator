"""Process management for the orchestrator."""

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, Optional

import psutil

from orchestrator.config import Config


@dataclass
class ProcessInfo:
    """Information about a managed process."""
    pid: int
    input_file: str
    output_file: str


class ProcessManager:
    """Manages the execution and monitoring of processes."""

    def __init__(self, config_obj: Config):
        """Initialize the process manager.

        Args:
            config_obj: Configuration object containing binary and directory
                settings.
        """
        self.config = config_obj
        self.process: Optional[ProcessInfo] = None

        # Setup logging
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def _build_command(self, input_file: str, output_file: str) -> list[str]:
        """Build command line arguments for the process.

        Args:
            input_file: Path to the input file.
            output_file: Path to the output file.

        Returns:
            List of command line arguments.
        """
        cmd = [self.config.binary.path]
        for flag in self.config.binary.flags:
            cmd.append(
                flag.format(
                    input_file=input_file,
                    output_file=output_file,
                ))
        return cmd

    def start_process(self, input_file: str) -> Optional[ProcessInfo]:
        """Start a new process to handle the input file.

        Args:
            input_file: Path to the input file to process.

        Returns:
            ProcessInfo if process started successfully, None otherwise.

        Raises:
            subprocess.SubprocessError: If process fails to start.
        """
        if not os.path.exists(input_file):
            self.logger.error("Input file not found: %s", input_file)
            return None

        # Create output filename based on input filename
        base_name = os.path.basename(input_file)
        output_file = os.path.join(self.config.directories.output_dir,
                                   f"{base_name}.output")

        # Ensure output directory exists
        os.makedirs(self.config.directories.output_dir, exist_ok=True)

        try:
            cmd = self._build_command(input_file, output_file)
            with subprocess.Popen(cmd,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  universal_newlines=True) as process:
                self.logger.info("Started process with PID: %d", process.pid)

                return ProcessInfo(pid=process.pid,
                                   input_file=input_file,
                                   output_file=output_file)
        except subprocess.SubprocessError as e:
            self.logger.error("Failed to start process: %s", e)
            raise

    def get_process_metrics(self, process_info: ProcessInfo) -> Dict:
        """Get current metrics for a process.

        Args:
            process_info: ProcessInfo object for the process to monitor.

        Returns:
            Dictionary containing process metrics.
        """
        try:
            proc = psutil.Process(process_info.pid)
            return {
                'cpu_percent': proc.cpu_percent(),
                'memory_rss': proc.memory_info().rss,
                'io_counters': proc.io_counters()._asdict()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.error("Failed to collect metrics for PID %d: %s",
                              process_info.pid, e)
            return {}

    def run(self):
        """Main run loop."""
        # Start the process
        input_file = sys.argv[1]
        self.process = self.start_process(input_file)

        try:
            while True:
                if self.process is None:
                    self.logger.error("Process has not been started")
                    break

                if self.process.pid is None:
                    self.logger.error("Process PID is None")
                    break

                metrics = self.get_process_metrics(self.process)
                self.logger.info("Process metrics: %s", metrics)
                time.sleep(1)  # Collect metrics every second

        except KeyboardInterrupt:
            self.logger.info("Shutting down orchestrator...")
            if self.process and self.process.pid is not None:
                proc = psutil.Process(self.process.pid)
                proc.terminate()
                proc.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py <path_to_input_file>")
        sys.exit(1)

    config = Config()
    orchestrator = ProcessManager(config)
    orchestrator.run()
