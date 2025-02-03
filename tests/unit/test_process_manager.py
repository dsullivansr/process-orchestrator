"""Unit tests for process management."""

import tempfile
import unittest
from unittest.mock import patch

from orchestrator.config import Config
from orchestrator.process_manager import ProcessManager


class TestProcessManager(unittest.TestCase):
    """Test process management functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test config
        self.test_config = {
            'binary': {
                'path': '/usr/bin/test',
                'flags': ['--input={input_file}', '--output={output_file}']
            },
            'directories': {
                'input_dir': '/tmp/input',
                'output_dir': '/tmp/output',
                'output_suffix': '.processed'
            }
        }
        self.config = Config(**self.test_config)
        self.manager = ProcessManager(self.config)

    def test_command_building(self):
        """Test command line argument building."""
        input_file = '/tmp/input/test.txt'
        output_file = '/tmp/output/test.txt.processed'
        # pylint: disable=protected-access
        cmd = self.manager._build_command(input_file, output_file)
        self.assertEqual(cmd, [
            '/usr/bin/test', '--input=/tmp/input/test.txt',
            '--output=/tmp/output/test.txt.processed'
        ])

    def test_start_process(self):
        """Test process start with valid input."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile() as temp_file:
            # Mock os.path.exists to return True
            with patch('os.path.exists', return_value=True):
                # Mock subprocess.Popen
                with patch('subprocess.Popen') as mock_popen:
                    mock_popen.return_value.__enter__.return_value.pid = 12345
                    process_info = self.manager.start_process(temp_file.name)

                    # Check process was started with correct arguments
                    self.assertIsNotNone(process_info)
                    self.assertEqual(process_info.pid, 12345)
                    self.assertEqual(process_info.input_file, temp_file.name)

    def test_start_process_nonexistent_file(self):
        """Test process start with nonexistent input file."""
        process_info = self.manager.start_process('/nonexistent/file.txt')
        self.assertIsNone(process_info)
