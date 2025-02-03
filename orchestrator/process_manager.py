"""Process management functionality."""

import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import psutil

from orchestrator.config import Config


class ProcessManager:
    """Process manager for handling file processing jobs."""

    def __init__(self, job_config: Config):
        """Initialize process manager.

        Args:
            job_config: Configuration for process management
        """
        self.config = job_config
        self.processes: Dict[str, psutil.Process] = {}

    def build_command(self, input_file: str) -> List[str]:
        """Build command for processing a file.

        Args:
            input_file: Path to input file

        Returns:
            List of command parts
        """
        output_file = self._get_output_path(input_file)
        command = [self.config.binary.path]

        # Add flags with templated values
        for flag in self.config.binary.flags:
            if '{input_file}' in flag:
                command.append(flag.replace('{input_file}', input_file))
            elif '{output_file}' in flag:
                command.append(flag.replace('{output_file}', output_file))
            else:
                command.append(flag)

        return command

    def _get_output_path(self, input_file: str) -> str:
        """Get output path for input file.

        Args:
            input_file: Path to input file

        Returns:
            Path to output file
        """
        basename = os.path.basename(input_file)
        if self.config.directories.output_suffix:
            basename = f"{basename}{self.config.directories.output_suffix}"
        return os.path.join(self.config.directories.output_dir, basename)

    def start_process(self, input_file: str) -> Optional[psutil.Process]:
        """Start a new process for file processing.

        Args:
            input_file: Path to input file

        Returns:
            Process info if started successfully, None otherwise

        Raises:
            FileNotFoundError: If input file does not exist
            ValueError: If process is already running for input file
            subprocess.SubprocessError: If process fails to start
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        if input_file in self.processes:
            raise ValueError(f"Process already running for {input_file}")

        command = self.build_command(input_file)
        try:
            with subprocess.Popen(command,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  universal_newlines=True) as process:
                self.processes[input_file] = psutil.Process(process.pid)
                return self.processes[input_file]
        except subprocess.SubprocessError as e:
            raise subprocess.SubprocessError(
                f"Failed to start process: {str(e)}") from e

    def get_process_info(self, input_file: str) -> Optional[Tuple[str, float]]:
        """Get process information.

        Args:
            input_file: Path to input file

        Returns:
            Tuple of (status, cpu_percent) if process exists, None otherwise
        """
        if input_file not in self.processes:
            return None

        try:
            process = self.processes[input_file]
            status = process.status()
            cpu_percent = process.cpu_percent()
            return status, cpu_percent
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            del self.processes[input_file]
            return None

    def get_active_processes(self) -> List[psutil.Process]:
        """Get list of active processes.

        Returns:
            List of active process objects
        """
        active_processes = []
        for input_file, process in list(self.processes.items()):
            try:
                if process.is_running():
                    active_processes.append(process)
                else:
                    del self.processes[input_file]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                del self.processes[input_file]
        return active_processes

    def stop_process(self, input_file: str) -> bool:
        """Stop a running process.

        Args:
            input_file: Path to input file

        Returns:
            True if process was stopped, False otherwise
        """
        if input_file not in self.processes:
            return False

        try:
            process = self.processes[input_file]
            process.terminate()
            process.wait(timeout=5)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        finally:
            del self.processes[input_file]

    def run(self):
        if len(sys.argv) != 2:
            print("Usage: python orchestrator.py <path_to_input_file>")
            sys.exit(1)

        input_file = sys.argv[1]
        self.start_process(input_file)


if __name__ == "__main__":
    ProcessManager(Config()).run()
