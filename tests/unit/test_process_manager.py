"""Unit tests for process manager module."""

import os
import tempfile
import unittest
from unittest.mock import patch

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager


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

        # Create test config
        self.test_config = {
            'binary': {
                'path': '/usr/bin/test',
                'flags': ['--input={input_file}', '--output={output_file}']
            },
            'directories': {
                'input_file_list': self.input_list_file,
                'output_dir': self.output_dir,
                'output_suffix': '.processed'
            }
        }
        self.config = Config(**self.test_config)
        self.manager = ProcessManager(self.config)

    def test_command_building(self):
        """Test building command with templates."""
        input_file = self.test_files[0]
        command = self.manager.build_command(input_file)
        expected = [
            '/usr/bin/test', f'--input={input_file}',
            f'--output={os.path.join(self.output_dir, os.path.basename(input_file) + ".processed")}'
        ]
        self.assertEqual(command, expected)

    def test_start_process(self):
        """Test starting a process."""
        # Mock subprocess.Popen
        with patch('subprocess.Popen') as mock_popen:
            mock_process = mock_popen.return_value
            mock_process.pid = 12345

            process = self.manager.start_process(self.test_files[0])

            # Check process was started with correct arguments
            self.assertIsNotNone(process)
            self.assertEqual(process.pid, 12345)

    def test_start_process_nonexistent_file(self):
        """Test starting a process with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            self.manager.start_process('/nonexistent/file.txt')
