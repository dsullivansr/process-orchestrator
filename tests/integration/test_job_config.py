"""Integration tests for job configuration loading and execution."""

import os
import tempfile
import time
import unittest
from typing import List

from orchestrator.config import Config, BinaryConfig, DirectoryConfig
from orchestrator.process_manager import ProcessManager


class TestJobConfig(unittest.TestCase):
    """Test job configuration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.input_files = self._create_test_files(['test1.txt', 'test2.txt'])
        self.input_list_file = os.path.join(self.test_dir, 'input_files.txt')
        self._create_input_list_file(self.input_files)
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.output_dir)

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

    def test_file_copy_job(self):
        """Test file copy job configuration."""
        config = Config(
            binary=BinaryConfig(path="/bin/cp",
                                flags=["{input_file}", "{output_file}"]),
            directories=DirectoryConfig(input_file_list=self.input_list_file,
                                        output_dir=self.output_dir))

        manager = ProcessManager(config)

        # Process each test file
        for test_file in self.input_files:
            process_info = manager.start_process(test_file)
            self.assertIsNotNone(process_info)

            # Wait for process to complete
            output_file = os.path.join(self.output_dir,
                                       os.path.basename(test_file))
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if os.path.exists(output_file):
                    break
                time.sleep(0.1)
            else:
                self.fail("Process did not complete in time")

            # Verify file was copied correctly
            self.assertTrue(os.path.exists(output_file))
            self.assertEqual(os.path.getsize(output_file),
                             os.path.getsize(test_file))

    def test_suffix_configurations(self):
        """Test output suffix configuration."""
        config = Config(
            binary=BinaryConfig(path="/bin/cp",
                                flags=["{input_file}", "{output_file}"]),
            directories=DirectoryConfig(input_file_list=self.input_list_file,
                                        output_dir=self.output_dir,
                                        output_suffix="_processed"))

        manager = ProcessManager(config)

        # Process a test file
        test_file = self.input_files[0]
        process_info = manager.start_process(test_file)
        self.assertIsNotNone(process_info)

        # Wait for process to complete
        output_file = os.path.join(self.output_dir,
                                   os.path.basename(test_file) + "_processed")
        timeout = 5
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(output_file):
                break
            time.sleep(0.1)
        else:
            self.fail("Process did not complete in time")

        # Verify file was copied correctly
        self.assertTrue(os.path.exists(output_file))
        self.assertEqual(os.path.getsize(output_file),
                         os.path.getsize(test_file))

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
            job_config = {
                'binary': {
                    'path': '/bin/cp',
                    'flags': ['{input_file}', '{output_file}']
                },
                'directories': {
                    'input_file_list': self.input_list_file,
                    'output_dir': output_dir,
                    'output_suffix': f'_bak{i}'
                }
            }

            config = Config(**job_config)
            manager = ProcessManager(config)

            # Process a test file
            test_file = self.input_files[0]
            process_info = manager.start_process(test_file)
            self.assertIsNotNone(process_info)

            # Verify output file exists in correct directory
            output_file = os.path.join(output_dir,
                                       os.path.basename(test_file) + f'_bak{i}')
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if os.path.exists(output_file):
                    break
                time.sleep(0.1)
            else:
                self.fail("Process did not complete in time")

            self.assertTrue(os.path.exists(output_file))

    def tearDown(self):
        """Clean up test fixtures."""
        os.system(f"rm -rf {self.test_dir}")
