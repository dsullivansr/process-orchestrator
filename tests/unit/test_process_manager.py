"""Tests for process management functionality."""

import tempfile
import unittest
from unittest.mock import Mock, patch

from orchestrator.config import Config, BinaryConfig, DirectoryConfig
from orchestrator.process_manager import ProcessManager


class TestProcessManager(unittest.TestCase):
    """Test cases for the ProcessManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.binary_config = BinaryConfig(
            path='/usr/bin/test',
            flags=['--input={input_file}', '--output={output_file}'])
        self.directory_config = DirectoryConfig(input_dir='/tmp/input',
                                                output_dir='/tmp/output')
        self.config = Config(binary=self.binary_config,
                             directories=self.directory_config)
        self.manager = ProcessManager(self.config)

    @patch('subprocess.Popen')
    def test_start_process(self, mock_popen):
        """Test starting a process with valid input."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile() as temp_file:
            # Mock the process
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.__enter__ = Mock(return_value=mock_process)
            mock_process.__exit__ = Mock(return_value=None)
            mock_popen.return_value = mock_process

            # Start the process
            process_info = self.manager.start_process(temp_file.name)

            # Verify process was started with correct arguments
            self.assertIsNotNone(process_info)
            self.assertEqual(process_info.pid, 12345)
            self.assertEqual(process_info.input_file, temp_file.name)
            self.assertTrue(process_info.output_file.endswith('.output'))

    def test_start_process_nonexistent_file(self):
        """Test starting a process with non-existent input file."""
        process_info = self.manager.start_process('/nonexistent/file')
        self.assertIsNone(process_info)

    def test_command_building(self):
        """Test building command line arguments."""
        input_file = '/path/to/input'
        output_file = '/path/to/output'

        cmd = self.manager._build_command(input_file, output_file)  # pylint: disable=protected-access

        self.assertEqual(cmd[0], self.config.binary.path)
        self.assertIn(f'--input={input_file}', cmd)
        self.assertIn(f'--output={output_file}', cmd)
