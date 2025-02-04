"""Unit tests for resource calibration functionality."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager
from orchestrator.resource_calibration import ResourceCalibrator, NoopCalibrator, ProcessCalibrator


class TestResourceCalibration(unittest.TestCase):
    """Test resource calibration functionality."""

    def _create_process_manager(
        self, input_list_file=None, output_dir=None, calibrator=None
    ):
        """Create a process manager instance.

        Args:
            input_list_file: Optional input list file path. If None, uses self.input_list_file
            output_dir: Optional output directory path. If None, uses self.output_dir
            calibrator: Optional resource calibrator. If None, uses NoopCalibrator.
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
        return ProcessManager(config, calibrator=calibrator)

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

    def test_interface_enforcement(self):
        """Test that ResourceCalibrator interface is enforced."""
        # Create a valid config for testing
        config = Config(
            binary={
                'path': '/bin/cat',
                'flags': ['{input_file}']
            },
            directories={
                'input_file_list': self.input_list_file,
                'output_dir': self.output_dir,
                'output_suffix': '.out'
            }
        )

        # Verify that ResourceCalibrator is an abstract class
        self.assertTrue(hasattr(ResourceCalibrator, '__abstractmethods__'))
        self.assertIn('calibrate', ResourceCalibrator.__abstractmethods__)

        # Define an incomplete calibrator class
        class IncompleteCalibrator(ResourceCalibrator):

            def __init__(self):
                pass

        # Verify incomplete class is still abstract
        self.assertTrue(hasattr(IncompleteCalibrator, '__abstractmethods__'))
        self.assertIn('calibrate', IncompleteCalibrator.__abstractmethods__)

        # Verify that implementing abstract method allows instantiation
        class ValidCalibrator(ResourceCalibrator):

            def __init__(self, config):
                self.config = config

            def calibrate(self, test_file):
                return None

        calibrator = ValidCalibrator(config)
        self.assertIsNotNone(calibrator)

    def test_noop_calibrator(self):
        """Test NoopCalibrator behavior."""
        calibrator = NoopCalibrator()
        # NoopCalibrator always returns None
        self.assertIsNone(calibrator.calibrate('test.txt'))

    def test_calibration_normal_case(self):
        """Test resource calibration under normal conditions."""
        with patch('psutil.Process') as mock_process, \
             patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_usage') as mock_disk_usage:
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

            # Create calibrator and verify thresholds
            config = Config(
                binary={
                    'path': '/bin/cat',  # Use cat for testing
                    'flags': ['{input_file}']
                },
                directories={
                    'input_file_list': self.input_list_file,
                    'output_dir': self.output_dir,
                    'output_suffix': '.out'
                }
            )
            calibrator = ProcessCalibrator(config)
            thresholds = calibrator.calibrate(self.test_file)

            # Verify the calculated thresholds
            self.assertIsNotNone(thresholds)
            self.assertAlmostEqual(
                thresholds['cpu_percent'], 60.0, places=0
            )  # 50% * 1.2
            memory_percent = (1024 * 1024 * 1024) / (
                16 * 1024 * 1024 * 1024
            ) * 100 * 1.2  # 1GB/16GB * 100 * 1.2
            self.assertAlmostEqual(thresholds['memory_percent'], memory_percent)
            disk_percent = len('Test content'
                               ) / (100 * 1024 * 1024 * 1024) * 100 * 1.2
            self.assertAlmostEqual(thresholds['disk_percent'], disk_percent)
            self.assertEqual(
                thresholds['max_processes'], 6
            )  # min(6, 12, 7812500000)

    def test_calibration_memory_constrained(self):
        """Test resource calibration when memory is the constraining factor."""
        with patch('psutil.Process') as mock_process, \
             patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_usage') as mock_disk_usage:
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

            # Create calibrator and verify thresholds
            config = Config(
                binary={
                    'path': '/bin/cat',  # Use cat for testing
                    'flags': ['{input_file}']
                },
                directories={
                    'input_file_list': self.input_list_file,
                    'output_dir': self.output_dir,
                    'output_suffix': '.out'
                }
            )
            calibrator = ProcessCalibrator(config)
            thresholds = calibrator.calibrate(self.test_file)

            # Verify the calculated thresholds
            self.assertIsNotNone(thresholds)
            self.assertAlmostEqual(
                thresholds['cpu_percent'], 60.0, places=0
            )  # 50% * 1.2
            memory_percent = (1024 * 1024 * 1024) / (
                8 * 1024 * 1024 * 1024
            ) * 100 * 1.2  # 1GB/8GB * 100 * 1.2
            self.assertAlmostEqual(thresholds['memory_percent'], memory_percent)
            disk_percent = len('Test content'
                               ) / (100 * 1024 * 1024 * 1024) * 100 * 1.2
            self.assertAlmostEqual(thresholds['disk_percent'], disk_percent)
            self.assertEqual(
                thresholds['max_processes'], 6
            )  # min(25, 6, 7812500000)

    def test_calibration_disk_constrained(self):
        """Test resource calibration when disk space is the constraining factor."""
        with patch('psutil.Process') as mock_process, \
             patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_usage') as mock_disk_usage:
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

            # Create calibrator and verify thresholds
            config = Config(
                binary={
                    'path': '/bin/cat',  # Use cat for testing
                    'flags': ['{input_file}']
                },
                directories={
                    'input_file_list': self.input_list_file,
                    'output_dir': self.output_dir,
                    'output_suffix': '.out'
                }
            )
            calibrator = ProcessCalibrator(config)
            thresholds = calibrator.calibrate(self.test_file)

            # Verify the calculated thresholds
            self.assertIsNotNone(thresholds)
            self.assertAlmostEqual(
                thresholds['cpu_percent'], 60.0, places=0
            )  # 50% * 1.2
            memory_percent = (512 * 1024 * 1024) / (
                64 * 1024 * 1024 * 1024
            ) * 100 * 1.2  # 512MB/64GB * 100 * 1.2
            self.assertAlmostEqual(thresholds['memory_percent'], memory_percent)
            disk_percent = (1024 * 1024 * 1024) / (
                5 * 1024 * 1024 * 1024
            ) * 100 * 1.2  # 1GB/5GB * 100 * 1.2
            self.assertAlmostEqual(thresholds['disk_percent'], disk_percent)
            self.assertEqual(thresholds['max_processes'], 4)  # min(25, 102, 4)

    def test_calibration_edge_cases(self):
        """Test resource calibration edge cases."""
        with patch('psutil.Process') as mock_process, \
             patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_usage') as mock_disk_usage:
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
            mock_process_instance.memory_info.return_value.rss = 1024  # 1KB
            mock_process.return_value = mock_process_instance

            # Create calibrator and verify thresholds
            config = Config(
                binary={
                    'path': '/bin/cat',  # Use cat for testing
                    'flags': ['{input_file}']
                },
                directories={
                    'input_file_list': self.input_list_file,
                    'output_dir': self.output_dir,
                    'output_suffix': '.out'
                }
            )
            calibrator = ProcessCalibrator(config)
            thresholds = calibrator.calibrate(self.test_file)

            # Verify the calculated thresholds use safe defaults
            self.assertIsNotNone(thresholds)
            self.assertEqual(
                thresholds['cpu_percent'], 1.2
            )  # 0% * 1.2 with minimum of 1%
            memory_percent = (1024 / 1024) * 100 * 1.2  # 1KB/1KB * 100 * 1.2
            self.assertAlmostEqual(thresholds['memory_percent'], memory_percent)
            disk_percent = len(
                'Test content'
            ) / 1024 * 100 * 1.2  # test content size/1KB * 100 * 1.2
            self.assertAlmostEqual(thresholds['disk_percent'], disk_percent)
            self.assertEqual(thresholds['max_processes'], 1)  # min(1, 1024, 78)

    def test_calibration_no_input_files(self):
        """Test resource calibration when no input files exist."""
        # Create empty input file list
        empty_list_file = os.path.join(self.test_dir, 'empty_list.txt')
        with open(empty_list_file, 'w', encoding='utf-8') as f:
            f.write('')

        # Create calibrator and verify it returns None for no input files
        config = Config(
            binary={
                'path': '/bin/cat',  # Use cat for testing
                'flags': ['{input_file}']
            },
            directories={
                'input_file_list': empty_list_file,
                'output_dir': self.output_dir,
                'output_suffix': '.out'
            }
        )
        calibrator = ProcessCalibrator(config)
        thresholds = calibrator.calibrate(None)
        self.assertIsNone(thresholds)
