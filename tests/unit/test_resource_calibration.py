"""Unit tests for resource calibration functionality."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager


class TestResourceCalibration(unittest.TestCase):
    """Test resource calibration functionality."""

    def _create_process_manager(
        self, input_list_file=None, output_dir=None, skip_calibration=False
    ):
        """Create a process manager instance.

        Args:
            input_list_file: Optional input list file path. If None, uses self.input_list_file
            output_dir: Optional output directory path. If None, uses self.output_dir
            skip_calibration: Whether to skip resource calibration
        """
        config = Config(
            binary={
                'path': '/bin/cat',  # Use cat for testing
                'flags': ['{input_file}']
            },
            directories={
                'input_file_list': input_list_file or self.input_list_file,
                'output_dir': output_dir or self.output_dir,
                'output_suffix': '.out'
            }
        )
        return ProcessManager(config, skip_calibration=skip_calibration)

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory and test files
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.test_dir, 'input')
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.input_dir)
        os.makedirs(self.output_dir)

        # Create test file
        self.test_file = os.path.join(self.input_dir, 'test.txt')
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write('Test content')

        # Create input file list
        self.input_list_file = os.path.join(self.test_dir, 'input_files.txt')
        with open(self.input_list_file, 'w', encoding='utf-8') as f:
            f.write(f'{self.test_file}\n')

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    @patch('psutil.Process')
    @patch('psutil.cpu_count')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_calibration_normal_case(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_count, mock_process
    ):
        """Test resource calibration under normal conditions."""
        # Mock system resource info
        mock_cpu_count.return_value = 8
        mock_virtual_memory.return_value.total = 16 * 1024 * 1024 * 1024  # 16GB
        mock_disk_usage.return_value.free = 100 * 1024 * 1024 * 1024  # 100GB

        # Mock process resource usage
        mock_process_instance = MagicMock()
        # Simulate stable CPU usage
        # Provide enough CPU values for all calls:
        # - Initial stabilization check (up to 10 attempts)
        # - Final measurement with interval
        # - Any additional checks
        mock_process_instance.cpu_percent.side_effect = [
            50.0,
            50.5,
            50.2,
            50.3,
            50.1,  # Initial values
            50.2,
            50.3,
            50.1,
            50.2,
            50.3,  # More initial values
            50.1,
            50.2,
            50.3,
            50.1,
            50.2,  # Final measurement
            50.1,
            50.2,
            50.3,
            50.1,
            50.2  # Extra values just in case
        ]
        mock_process_instance.memory_info.return_value.rss = 1024 * 1024 * 1024  # 1GB
        mock_process.return_value = mock_process_instance

        # Create process manager and verify thresholds
        manager = self._create_process_manager()

        # Verify the calculated thresholds
        self.assertEqual(
            manager.resource_monitor.thresholds['cpu_percent'], 80.0
        )
        self.assertEqual(
            manager.resource_monitor.thresholds['memory_percent'], 80.0
        )
        self.assertEqual(
            manager.resource_monitor.thresholds['disk_percent'], 80.0
        )
        self.assertEqual(
            manager.resource_monitor.thresholds['max_processes'], 6
        )  # 8 cores * 0.8 = 6

    @patch('psutil.Process')
    @patch('psutil.cpu_count')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_calibration_memory_constrained(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_count, mock_process
    ):
        """Test resource calibration when memory is the constraining factor."""
        # Mock system resource info
        mock_cpu_count.return_value = 32
        mock_virtual_memory.return_value.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_disk_usage.return_value.free = 100 * 1024 * 1024 * 1024  # 100GB

        # Mock process resource usage
        mock_process_instance = MagicMock()
        # Simulate stable CPU usage
        # Provide enough CPU values for all calls:
        # - Initial stabilization check (up to 10 attempts)
        # - Final measurement with interval
        # - Any additional checks
        mock_process_instance.cpu_percent.side_effect = [
            50.0,
            50.5,
            50.2,
            50.3,
            50.1,  # Initial values
            50.2,
            50.3,
            50.1,
            50.2,
            50.3,  # More initial values
            50.1,
            50.2,
            50.3,
            50.1,
            50.2,  # Final measurement
            50.1,
            50.2,
            50.3,
            50.1,
            50.2  # Extra values just in case
        ]
        mock_process_instance.memory_info.return_value.rss = 1024 * 1024 * 1024  # 1GB
        mock_process.return_value = mock_process_instance

        # Create process manager and verify memory limits
        manager = self._create_process_manager()

        # Memory should be the limiting factor: 8GB * 0.8 / 1GB = 6 processes
        self.assertEqual(
            manager.resource_monitor.thresholds['max_processes'], 6
        )

    @patch('psutil.Process')
    @patch('psutil.cpu_count')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_calibration_disk_constrained(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_count, mock_process
    ):
        """Test resource calibration when disk space is the constraining factor."""
        # Mock system resource info
        mock_cpu_count.return_value = 32
        mock_virtual_memory.return_value.total = 64 * 1024 * 1024 * 1024  # 64GB
        mock_disk_usage.return_value.free = 5 * 1024 * 1024 * 1024  # 5GB

        # Mock process resource usage
        mock_process_instance = MagicMock()
        # Simulate stable CPU usage
        # Provide enough CPU values for all calls:
        # - Initial stabilization check (up to 10 attempts)
        # - Final measurement with interval
        # - Any additional checks
        mock_process_instance.cpu_percent.side_effect = [
            50.0,
            50.5,
            50.2,
            50.3,
            50.1,  # Initial values
            50.2,
            50.3,
            50.1,
            50.2,
            50.3,  # More initial values
            50.1,
            50.2,
            50.3,
            50.1,
            50.2,  # Final measurement
            50.1,
            50.2,
            50.3,
            50.1,
            50.2  # Extra values just in case
        ]
        mock_process_instance.memory_info.return_value.rss = 512 * 1024 * 1024  # 512MB
        mock_process.return_value = mock_process_instance

        # Create a 1GB test file
        with open(self.test_file, 'wb') as f:
            f.write(b'0' * (1024 * 1024 * 1024))

        # Create process manager and verify disk limits
        manager = self._create_process_manager()

        # Disk should be the limiting factor: 5GB * 0.8 / (1GB * 2) = 2 processes
        self.assertEqual(
            manager.resource_monitor.thresholds['max_processes'], 2
        )

    @patch('psutil.Process')
    @patch('psutil.cpu_count')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_calibration_edge_cases(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_count, mock_process
    ):
        """Test resource calibration edge cases."""
        # Mock system resource info with edge case values
        mock_cpu_count.return_value = None  # CPU count not available
        mock_virtual_memory.return_value.total = 1024  # Very small memory
        mock_disk_usage.return_value.free = 1024  # Very small disk space

        # Mock process with zero resource usage
        mock_process_instance = MagicMock()
        # Simulate stable CPU usage at zero
        mock_process_instance.cpu_percent.side_effect = [
            0.0, 0.1, 0.0, 0.1, 0.0
        ]
        mock_process_instance.memory_info.return_value.rss = 0
        mock_process.return_value = mock_process_instance

        # Create process manager and verify safe defaults
        manager = self._create_process_manager()

        # Should default to safe values
        self.assertGreater(
            manager.resource_monitor.thresholds['max_processes'], 0
        )
        self.assertLessEqual(
            manager.resource_monitor.thresholds['max_processes'], 1
        )

    def test_calibration_no_input_files(self):
        """Test resource calibration when no input files exist."""
        # Create empty input file list
        empty_list_file = os.path.join(self.test_dir, 'empty_list.txt')
        with open(empty_list_file, 'w', encoding='utf-8') as f:
            f.write('')

        # Create process manager with empty list
        manager = self._create_process_manager(input_list_file=empty_list_file)

        # Should use default values from config
        self.assertEqual(
            manager.resource_monitor.thresholds['max_processes'],
            manager.config.resources.max_processes
        )
