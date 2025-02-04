"""Unit tests for the orchestrator module."""

import os
import tempfile
import unittest
from orchestrator.config import Config, BinaryConfig, DirectoryConfig


class TestOrchestrator(unittest.TestCase):
    """Test cases for the Orchestrator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.input_list_file = os.path.join(self.test_dir, 'input_files.txt')
        self.output_dir = os.path.join(self.test_dir, 'output')

        # Create input file list
        with open(self.input_list_file, 'w', encoding='utf-8') as f:
            f.write('/path/to/test1.txt\n')
            f.write('/path/to/test2.txt\n')

        binary = BinaryConfig(path="/bin/echo", flags=["-n"])
        directories = DirectoryConfig(
            input_file_list=self.input_list_file, output_dir=self.output_dir
        )
        self.config = Config(binary=binary, directories=directories)

    def test_initialization(self):
        """Test that the orchestrator initializes correctly."""
        self.assertIsNotNone(self.config)
        self.assertEqual(self.config.binary.path, "/bin/echo")
        self.assertEqual(
            self.config.directories.input_file_list, self.input_list_file
        )
        self.assertEqual(self.config.directories.output_dir, self.output_dir)


if __name__ == '__main__':
    unittest.main()
