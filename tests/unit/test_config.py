"""Unit tests for configuration module."""

import os
import tempfile
import unittest

from orchestrator.config import Config


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.input_list_file = os.path.join(self.test_dir, 'input_files.txt')
        self.output_dir = os.path.join(self.test_dir, 'output')

        # Create test input list file
        with open(self.input_list_file, 'w', encoding='utf-8') as f:
            f.write('/path/to/file1.txt\n')
            f.write('/path/to/file2.txt\n')

    def test_load_config_from_file(self):
        """Test loading configuration from YAML file."""
        config_path = os.path.join(self.test_dir, 'config.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(
                f'''
binary:
  path: /bin/cp
  flags:
    - "{{input_file}}"
    - "{{output_file}}"
directories:
  input_file_list: {self.input_list_file}
  output_dir: {self.output_dir}
  output_suffix: _processed
'''
            )

        config = Config.from_yaml(config_path)
        self.assertEqual(config.binary.path, '/bin/cp')
        self.assertEqual(config.binary.flags, ['{input_file}', '{output_file}'])
        self.assertEqual(
            config.directories.input_file_list, self.input_list_file
        )
        self.assertEqual(config.directories.output_dir, self.output_dir)
        self.assertEqual(config.directories.output_suffix, '_processed')

    def test_load_config_missing_file(self):
        """Test loading configuration from non-existent file."""
        with self.assertRaises(FileNotFoundError):
            Config.from_yaml('/nonexistent/config.yaml')

    def test_load_config_with_kwargs(self):
        """Test loading configuration with keyword arguments."""
        config = Config(
            binary={
                'path': '/bin/cp',
                'flags': ['{input_file}', '{output_file}']
            },
            directories={
                'input_file_list': self.input_list_file,
                'output_dir': self.output_dir,
                'output_suffix': '_processed'
            }
        )

        self.assertEqual(config.binary.path, '/bin/cp')
        self.assertEqual(config.binary.flags, ['{input_file}', '{output_file}'])
        self.assertEqual(
            config.directories.input_file_list, self.input_list_file
        )
        self.assertEqual(config.directories.output_dir, self.output_dir)
        self.assertEqual(config.directories.output_suffix, '_processed')

    def tearDown(self):
        """Clean up test fixtures."""
        os.system(f"rm -rf {self.test_dir}")
