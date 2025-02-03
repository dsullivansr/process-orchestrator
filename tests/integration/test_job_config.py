"""Integration tests for job configuration loading and execution."""

import os
import tempfile
import time
import unittest
from typing import List

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager


class TestJobConfig(unittest.TestCase):
    """Test job configuration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories
        self.temp_base = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.temp_base, 'input')
        self.output_dir = os.path.join(self.temp_base, 'output')
        os.makedirs(self.input_dir)
        os.makedirs(self.output_dir)

        # Create test files
        self.test_files: List[str] = []
        for i in range(3):
            test_file = os.path.join(self.input_dir, f'test_{i}.txt')
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(f'Test content {i}')
            self.test_files.append(test_file)

        # Define job configurations
        self.job_configs = {
            'binary': {
                'path': '/bin/cp',
                'flags': ['{input_file}', '{output_file}']
            },
            'directories': {
                'input_dir': self.input_dir,
                'output_dir': self.output_dir,
                'output_suffix': '.bak'
            }
        }

    def test_file_copy_job(self):
        """Test file copy job configuration."""
        # Initialize process manager with config
        config = Config(**self.job_configs)
        manager = ProcessManager(config)

        # Process each test file
        for test_file in self.test_files:
            process_info = manager.start_process(test_file)
            self.assertIsNotNone(process_info)

            # Wait for process to complete
            output_file = os.path.join(self.output_dir,
                                       os.path.basename(test_file) + '.bak')
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
        invalid_config = self.job_configs.copy()
        invalid_config['binary'] = {'flags': []}
        with self.assertRaises(ValueError):
            Config(**invalid_config)

        # Test with missing input directory
        invalid_config = self.job_configs.copy()
        invalid_config['directories'] = {'output_dir': self.output_dir}
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
            job_config = self.job_configs.copy()
            job_config['directories'] = {
                'input_dir': self.input_dir,
                'output_dir': output_dir,
                'output_suffix': f'.bak{i}'
            }

            config = Config(**job_config)
            manager = ProcessManager(config)

            # Process a test file
            test_file = self.test_files[0]
            process_info = manager.start_process(test_file)
            self.assertIsNotNone(process_info)

            # Verify output file exists in correct directory
            output_file = os.path.join(output_dir,
                                       os.path.basename(test_file) + f'.bak{i}')
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if os.path.exists(output_file):
                    break
                time.sleep(0.1)
            else:
                self.fail("Process did not complete in time")

            self.assertTrue(os.path.exists(output_file))

    def test_same_directory_validation(self):
        """Test validation when input and output directories are the same."""
        # Test with same directory but no suffix
        job_config = self.job_configs.copy()
        job_config['directories'] = {
            'input_dir': self.input_dir,
            'output_dir': self.input_dir,
            'output_suffix': ''  # No suffix
        }

        with self.assertRaises(ValueError):
            Config(**job_config)

    def test_suffix_configurations(self):
        """Test different output suffix configurations."""
        # Test without suffix
        job_config = self.job_configs.copy()
        job_config['directories'] = {
            'input_dir': self.temp_base,
            'output_dir': os.path.join(self.temp_base, 'output'),
            'output_suffix': ''  # No suffix, but different directories
        }

        config = Config(**job_config)
        manager = ProcessManager(config)

        # Process a test file
        test_file = self.test_files[0]
        process_info = manager.start_process(test_file)
        self.assertIsNotNone(process_info)

        # Wait for process to complete
        output_file = os.path.join(os.path.join(self.temp_base, 'output'),
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

    def tearDown(self):
        """Clean up test fixtures."""
        os.system(f"rm -rf {self.temp_base}")
