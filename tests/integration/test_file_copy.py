"""Integration tests for file copy functionality."""

import os
import tempfile
import time
import unittest
from typing import List

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager


class TestFileCopy(unittest.TestCase):
    """Test file copying functionality."""

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

        # Create a large test file (1MB)
        self.large_file = os.path.join(self.input_dir, 'large_file.txt')
        with open(self.large_file, 'wb') as f:
            f.write(b'0' * 1024 * 1024)

        # Initialize process manager
        config = Config(
            **{
                'binary': {
                    'path': '/bin/cp',
                    'flags': ['{input_file}', '{output_file}']
                },
                'directories': {
                    'input_dir': self.input_dir,
                    'output_dir': self.output_dir,
                    'output_suffix': '.bak'
                }
            })
        self.manager = ProcessManager(config)

    def test_large_file(self):
        """Test copying a large file."""
        process_info = self.manager.start_process(self.large_file)
        self.assertIsNotNone(process_info)

        # Wait for process to complete
        output_file = os.path.join(self.output_dir,
                                   os.path.basename(self.large_file) + '.bak')
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
                         os.path.getsize(self.large_file))

    def test_nonexistent_file(self):
        """Test copying a non-existent file."""
        process_info = self.manager.start_process('/nonexistent/file.txt')
        self.assertIsNone(process_info)

    def test_parallel_file_copy(self):
        """Test copying multiple files in parallel."""
        processes = []
        for test_file in self.test_files:
            process_info = self.manager.start_process(test_file)
            self.assertIsNotNone(process_info)
            processes.append(process_info)

        # Wait for all processes to complete
        timeout = 5
        start_time = time.time()
        while time.time() - start_time < timeout:
            all_done = True
            for test_file in self.test_files:
                output_file = os.path.join(self.output_dir,
                                           os.path.basename(test_file) + '.bak')
                if not os.path.exists(output_file):
                    all_done = False
                    break
            if all_done:
                break
            time.sleep(0.1)
        else:
            self.fail("Not all processes completed in time")

        # Verify all files were copied correctly
        for test_file in self.test_files:
            output_file = os.path.join(self.output_dir,
                                       os.path.basename(test_file) + '.bak')
            self.assertTrue(os.path.exists(output_file))
            self.assertEqual(os.path.getsize(output_file),
                             os.path.getsize(test_file))

    def tearDown(self):
        """Clean up test fixtures."""
        os.system(f"rm -rf {self.temp_base}")
