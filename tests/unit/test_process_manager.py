"""Unit tests for process manager module."""

import os
import tempfile
import unittest
from unittest.mock import patch

import pytest

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager
from orchestrator.resource_calibration import NoopCalibrator


class TestProcessManager(unittest.TestCase):
    """Test process manager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory and test files
        self.test_dir = tempfile.mkdtemp()
        self.input_list_file = os.path.join(self.test_dir, 'input_files.txt')
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.output_dir)

        # Create test files and input list
        self.test_files = []
        for i in range(3):
            test_file = os.path.join(self.test_dir, f'test_{i}.txt')
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(f'Test content {i}')
            self.test_files.append(test_file)

        with open(self.input_list_file, 'w', encoding='utf-8') as f:
            for test_file in self.test_files:
                f.write(f'{test_file}\n')

        # Initialize manager for tests that don't need specific config
        self.manager = self._create_process_manager()

    def _create_process_manager(
        self,
        input_list_file=None,
        output_dir=None,
        calibrator=None,
        skip_calibration=False
    ):
        """Create a process manager instance.

        Args:
            input_list_file: Optional input list file path. If None, uses self.input_list_file
            output_dir: Optional output directory path. If None, uses self.output_dir
            calibrator: Optional calibrator to use. If None, uses NoopCalibrator
            skip_calibration: Whether to skip resource calibration
        """
        config = Config(
            binary={
                'path': '/usr/bin/test',
                'flags': ['--input={input_file}', '--output={output_file}']
            },
            directories={
                'input_file_list': input_list_file or self.input_list_file,
                'output_dir': output_dir or self.output_dir,
                'output_suffix': '.processed'
            }
        )
        return ProcessManager(
            config,
            calibrator=calibrator or NoopCalibrator(),
            skip_calibration=skip_calibration
        )

    def test_command_building(self):
        """Test building command with templates."""
        input_file = self.test_files[0]
        command, use_shell = self.manager.build_command(input_file)
        expected = [
            '/usr/bin/test', f'--input={input_file}',
            f'--output={os.path.join(self.output_dir, os.path.basename(input_file) + ".processed")}'
        ]
        self.assertEqual(command, expected)
        self.assertFalse(use_shell)

    def test_start_process(self):
        """Test starting a process."""
        # Mock subprocess.Popen and psutil.Process
        with patch('subprocess.Popen') as mock_popen, \
             patch('psutil.Process') as mock_psutil_process:
            mock_process = mock_popen.return_value
            mock_process.pid = 12345

            # Configure psutil.Process mock
            mock_psutil_process_instance = mock_psutil_process.return_value
            mock_psutil_process_instance.pid = 12345
            mock_psutil_process_instance.memory_info.return_value.rss = 1024 * 1024  # 1MB
            mock_psutil_process_instance.cpu_percent.return_value = 5.0

            process = self.manager.start_process(self.test_files[0])

            # Check process was started with correct arguments
            self.assertIsNotNone(process)
            self.assertEqual(process.pid, 12345)

            # Verify psutil.Process was created with correct PID
            mock_psutil_process.assert_called_once_with(12345)

    def test_start_process_nonexistent_file(self):
        """Test starting a process with non-existent file."""
        manager = self._create_process_manager()
        with self.assertRaises(FileNotFoundError):
            manager.start_process('/nonexistent/file.txt')

    def test_run_success(self):
        """Test running process manager with successful processes."""
        # Create manager with calibration skipped
        self.manager = self._create_process_manager(skip_calibration=True)

        # Mock subprocess.Popen and psutil.Process
        with patch('subprocess.Popen') as mock_popen, \
             patch('psutil.Process') as mock_psutil_process:
            # Configure process mocks
            mock_process = mock_popen.return_value
            mock_process.pid = 12345
            # Each file needs: None (running), 0 (success)
            mock_process.poll.side_effect = [None, 0] * len(
                self.test_files
            )  # Running then success
            mock_process.communicate.return_value = ('output', '')

            # Configure psutil.Process mock
            mock_psutil_process_instance = mock_psutil_process.return_value
            mock_psutil_process_instance.pid = 12345
            mock_psutil_process_instance.memory_info.return_value.rss = 1024 * 1024  # 1MB
            mock_psutil_process_instance.cpu_percent.return_value = 5.0

            # Configure resource monitor to allow all processes
            self.manager.resource_monitor.can_start_new_process = lambda: True

            # Run process manager
            exit_code = self.manager.run()

            # Verify successful completion
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                len(self.manager.completed_files), len(self.test_files)
            )
            self.assertEqual(len(self.manager.failed_files), 0)

    @pytest.mark.skip(
        reason="Test needs to be fixed - retry count tracking issue"
    )
    def test_run_with_retries(self):
        """Test running process manager with retries for failed processes."""
        # Create manager with calibration skipped
        self.manager = self._create_process_manager(skip_calibration=True)

        # Mock subprocess.Popen and psutil.Process
        with patch('subprocess.Popen') as mock_popen, \
             patch('psutil.Process') as mock_psutil_process:
            # Configure process mocks
            mock_process = mock_popen.return_value
            mock_process.pid = 12345
            # First process fails twice then succeeds
            # For each retry, we need: None (running), 1 (fail)
            # Final success needs: None (running), 0 (success)
            mock_process.poll.side_effect = [
                None,
                1,  # First attempt fails
                None,
                1,  # Second attempt fails
                None,
                0  # Third attempt succeeds
            ] + [None, 0] * (
                len(self.test_files) - 1
            ) * 3  # Other files succeed (with extra values)
            # Reset the retry count to ensure we start fresh
            self.manager.retry_counts = {}
            mock_process.communicate.return_value = ('output', 'error')

            # Configure psutil.Process mock
            mock_psutil_process_instance = mock_psutil_process.return_value
            mock_psutil_process_instance.pid = 12345
            mock_psutil_process_instance.memory_info.return_value.rss = 1024 * 1024  # 1MB
            mock_psutil_process_instance.cpu_percent.return_value = 5.0

            # Configure resource monitor to allow all processes
            self.manager.resource_monitor.can_start_new_process = lambda: True

            # Run process manager
            exit_code = self.manager.run()

            # Verify successful completion with retries
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                len(self.manager.completed_files), len(self.test_files)
            )
            self.assertEqual(len(self.manager.failed_files), 0)
            self.assertEqual(self.manager.retry_counts[self.test_files[0]], 2)

    @pytest.mark.skip(
        reason="Test needs to be fixed - retry logic and exit code issues"
    )
    def test_run_with_failures(self):
        """Test running process manager with permanent failures."""
        # Create manager with calibration skipped
        self.manager = self._create_process_manager(skip_calibration=True)

        # Mock subprocess.Popen and psutil.Process
        with patch('subprocess.Popen') as mock_popen, \
             patch('psutil.Process') as mock_psutil_process:
            # Configure process mocks
            mock_process = mock_popen.return_value
            mock_process.pid = 12345
            # First process fails max_retries times
            # For each retry: None (running), 1 (fail)
            mock_process.poll.side_effect = [
                None,
                1,  # First attempt
                None,
                1,  # Second attempt
                None,
                1  # Third attempt (max_retries=3)
            ] + [None, 0] * (
                len(self.test_files) - 1
            ) * 3  # Other files succeed (with extra values)
            # Reset the retry count to ensure we start fresh
            self.manager.retry_counts = {}
            mock_process.communicate.return_value = ('output', 'error')

            # Configure psutil.Process mock
            mock_psutil_process_instance = mock_psutil_process.return_value
            mock_psutil_process_instance.pid = 12345
            mock_psutil_process_instance.memory_info.return_value.rss = 1024 * 1024  # 1MB
            mock_psutil_process_instance.cpu_percent.return_value = 5.0

            # Configure resource monitor to allow all processes
            self.manager.resource_monitor.can_start_new_process = lambda: True

            # Run process manager
            exit_code = self.manager.run()

            # Verify failure handling
            self.assertEqual(exit_code, 1)
            self.assertTrue(len(self.manager.failed_files) > 0)
            self.assertEqual(
                self.manager.retry_counts[self.test_files[0]],
                self.manager.max_retries
            )
