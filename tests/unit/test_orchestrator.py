"""Unit tests for the orchestrator module."""

import unittest
from orchestrator.config import Config, BinaryConfig, DirectoryConfig


class TestOrchestrator(unittest.TestCase):
    """Test cases for the Orchestrator class."""

    def setUp(self):
        """Set up test fixtures."""
        binary = BinaryConfig(path="/bin/echo", flags=["-n"])
        directories = DirectoryConfig(input_dir="/tmp/in",
                                      output_dir="/tmp/out")
        self.config = Config(binary=binary, directories=directories)

    def test_initialization(self):
        """Test that the orchestrator initializes correctly."""
        self.assertIsNotNone(self.config)
        self.assertEqual(self.config.binary.path, "/bin/echo")
        self.assertEqual(self.config.directories.input_dir, "/tmp/in")


if __name__ == '__main__':
    unittest.main()
