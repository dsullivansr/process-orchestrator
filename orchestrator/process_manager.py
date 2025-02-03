"""Process Manager module for handling process execution and monitoring."""

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

from psutil import Process, NoSuchProcess, AccessDenied

from orchestrator.config import Config


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    input_file: str
    output_file: str


class ProcessManager:
    """Manages process execution and monitoring."""

    def __init__(self, config_obj: Config):
        """Initialize the process manager.

        Args:
            config_obj: Configuration object containing binary and directory settings
        """
        self.config = config_obj
        self.process = None
        self.logger = logging.getLogger(__name__)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    def _build_command(self, input_file: str, output_file: str) -> List[str]:
        """Build command line arguments.

        Args:
            input_file: Path to the input file
            output_file: Path to the output file

        Returns:
            List of command line arguments
        """
        cmd = [self.config.binary.path]
        for flag in self.config.binary.flags:
            if '{input_file}' in flag:
                cmd.append(flag.replace('{input_file}', input_file))
            elif '{output_file}' in flag:
                cmd.append(flag.replace('{output_file}', output_file))
            else:
                cmd.append(flag)
        return cmd

    def _get_output_path(self, input_file: str) -> str:
        """Generate output file path based on input file and configuration.

        Args:
            input_file: Path to the input file

        Returns:
            Path to the output file
        """
        base_name = os.path.basename(input_file)
        if self.config.directories.output_suffix:
            base_name += self.config.directories.output_suffix
        return os.path.join(self.config.directories.output_dir, base_name)

    def start_process(self, input_file: str) -> Optional[ProcessInfo]:
        """Start a new process.

        Args:
            input_file: Path to the input file

        Returns:
            ProcessInfo object if process started successfully, None otherwise

        Raises:
            ValueError: If input and output files would be the same
        """
        if not os.path.exists(input_file):
            self.logger.error("Input file does not exist: %s", input_file)
            return None

        output_file = self._get_output_path(input_file)

        if os.path.abspath(input_file) == os.path.abspath(output_file):
            raise ValueError(
                f"Input and output files would be the same: {input_file}")

        os.makedirs(self.config.directories.output_dir, exist_ok=True)

        try:
            cmd = self._build_command(input_file, output_file)
            with subprocess.Popen(cmd,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  universal_newlines=True) as process:
                self.process = ProcessInfo(pid=process.pid,
                                           input_file=input_file,
                                           output_file=output_file)
                self.logger.info("Started process with PID: %d", process.pid)
                return self.process
        except Exception as e:
            self.logger.error("Failed to start process: %s", str(e))
            return None

    def get_process_metrics(self, process_info: ProcessInfo) -> dict:
        """Get current metrics for a process.

        Args:
            process_info: Process to get metrics for.

        Returns:
            Dictionary containing process metrics.
        """
        try:
            proc = Process(process_info.pid)
            return {
                'cpu_percent': proc.cpu_percent(),
                'memory_rss': proc.memory_info().rss,
                'status': proc.status()
            }
        except (NoSuchProcess, AccessDenied) as e:
            self.logger.error("Failed to collect metrics for PID %d: %s",
                              process_info.pid, e)
            return {}

    def run(self):
        """Main run loop."""
        # Start the process
        input_file = sys.argv[1]
        self.start_process(input_file)

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
                proc = Process(self.process.pid)
                proc.terminate()
                proc.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py <path_to_input_file>")
        sys.exit(1)

    config = Config.load_from_file('config.json')
    orchestrator = ProcessManager(config)
    orchestrator.run()
