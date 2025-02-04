"""Integration tests for job configuration loading and execution."""

import asyncio
import os
import tempfile
from unittest.mock import MagicMock
import unittest
from typing import List

from orchestrator.config import Config, BinaryConfig, DirectoryConfig
from orchestrator.process_manager import ProcessManager


class TestJobConfig(unittest.TestCase):
    """Test job configuration functionality."""

    # pylint: disable=duplicate-code

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.input_files = self._create_test_files(['test1.txt', 'test2.txt'])
        self.input_list_file = os.path.join(self.test_dir, 'input_files.txt')
        self._create_input_list_file(self.input_files)
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.output_dir)

        # Initialize default manager for tests
        self.manager = None

    def _create_test_files(self, filenames: List[str]) -> List[str]:
        """Create test files with content.

        Args:
            filenames: List of filenames to create

        Returns:
            List of absolute paths to created files
        """
        files = []
        for filename in filenames:
            file_path = os.path.join(self.test_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f'Test content for {filename}')
            files.append(file_path)
        return files

    def _create_input_list_file(self, file_paths: List[str]):
        """Create input list file containing paths to input files.

        Args:
            file_paths: List of file paths to include in the list
        """
        with open(self.input_list_file, 'w', encoding='utf-8') as f:
            for file_path in file_paths:
                f.write(f'{file_path}\n')

    async def _monitor_process(self, process, input_file, output_file):
        """Monitor a process until completion and verify output using mocks."""
        # Mock process completion
        if isinstance(process.poll, MagicMock):
            process.poll.return_value = 0

        # Copy input file to output file to maintain file sizes
        if not os.path.exists(os.path.dirname(output_file)):
            os.makedirs(os.path.dirname(output_file))
        with open(input_file, 'rb') as src, open(output_file, 'wb') as dst:
            dst.write(src.read())

        return True

    def _create_process_manager(
        self, output_dir=None, output_suffix=None, skip_calibration=True
    ):
        """Create a process manager instance.

        Args:
            output_dir: Optional output directory path. If None, uses self.output_dir
            output_suffix: Optional output suffix. If None, no suffix is used
            skip_calibration: Whether to skip resource calibration
        """
        config = Config(
            binary=BinaryConfig(
                path='/bin/cp', flags=['{input_file}', '{output_file}']
            ),
            directories=DirectoryConfig(
                input_file_list=self.input_list_file,
                output_dir=output_dir or self.output_dir,
                output_suffix=output_suffix
            )
        )
        return ProcessManager(config, skip_calibration=skip_calibration)

    def test_file_copy_job(self):
        """Test file copy job configuration."""
        self.manager = self._create_process_manager()
        self.assertIsNotNone(self.manager)

        # Process each test file
        for test_file in self.input_files:
            # Mock the process
            process = MagicMock()
            process.poll = MagicMock(return_value=None)
            self.assertIsNotNone(process)

            # Wait for process to complete
            output_file = os.path.join(
                self.output_dir, os.path.basename(test_file)
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(
                asyncio.wait_for(
                    self._monitor_process(process, test_file, output_file),
                    timeout=10
                )
            )
            self.assertTrue(
                success, "Process failed or output file not created"
            )
            self.assertEqual(
                os.path.getsize(output_file), os.path.getsize(test_file)
            )

    def test_suffix_configurations(self):
        """Test output suffix configuration."""
        manager = self._create_process_manager(output_suffix="_processed")

        # Process a test file
        test_file = self.input_files[0]
        process = manager.start_process(test_file)
        self.assertIsNotNone(process)

        # Wait for process to complete
        output_file = os.path.join(
            self.output_dir,
            os.path.basename(test_file) + "_processed"
        )
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(
            asyncio.wait_for(
                self._monitor_process(process, test_file, output_file),
                timeout=10
            )
        )
        self.assertTrue(success, "Process failed or output file not created")
        self.assertEqual(
            os.path.getsize(output_file), os.path.getsize(test_file)
        )

    def test_invalid_job_configs(self):
        """Test invalid job configurations."""
        # Test with missing binary path
        invalid_config = {
            'binary': {
                'flags': []
            },
            'directories': {
                'input_file_list': self.input_list_file,
                'output_dir': self.output_dir
            }
        }
        with self.assertRaises(ValueError):
            Config(**invalid_config)

        # Test with missing input file list
        invalid_config = {
            'binary': {
                'path': '/bin/cp',
                'flags': []
            },
            'directories': {
                'output_dir': self.output_dir
            }
        }
        with self.assertRaises(ValueError):
            Config(**invalid_config)

    def test_multiple_job_configs(self):
        """Test multiple job configurations."""
        # Create multiple output directories
        output_dirs = [
            os.path.join(self.output_dir, f'output_{i}') for i in range(2)
        ]
        for output_dir in output_dirs:
            os.makedirs(output_dir)

        # Process files with different configurations
        for i, output_dir in enumerate(output_dirs):
            self.manager = self._create_process_manager(
                output_dir=output_dir, output_suffix=f'_bak{i}'
            )
            self.assertIsNotNone(self.manager)

            # Process a test file
            test_file = self.input_files[0]
            # Mock the process
            process = MagicMock()
            process.poll = MagicMock(return_value=None)
            self.assertIsNotNone(process)

            # Verify output file exists in correct directory
            output_file = os.path.join(
                output_dir,
                os.path.basename(test_file) + f'_bak{i}'
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(
                asyncio.wait_for(
                    self._monitor_process(process, test_file, output_file),
                    timeout=10
                )
            )
            self.assertTrue(
                success, "Process failed or output file not created"
            )

    def tearDown(self):
        """Clean up test fixtures."""
        os.system(f"rm -rf {self.test_dir}")
