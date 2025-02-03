"""Unit tests for configuration management."""

import os
import tempfile
import unittest

import yaml

from orchestrator.config import Config


class TestConfig(unittest.TestCase):
    """Test configuration loading and validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'binary': {
                'path': '/bin/cp',
                'flags': ['{input_file}', '{output_file}']
            },
            'directories': {
                'input_dir': '/data/input',
                'output_dir': '/data/output',
                'output_suffix': '.bak'
            }
        }

        # Create test config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.test_config, f)

    def test_load_config_from_file(self):
        """Test loading configuration from a YAML file."""
        config = Config.load_from_file(self.config_path)
        self.assertEqual(config.binary.path, '/bin/cp')
        self.assertEqual(config.binary.flags, ['{input_file}', '{output_file}'])
        self.assertEqual(config.directories.input_dir, '/data/input')
        self.assertEqual(config.directories.output_dir, '/data/output')
        self.assertEqual(config.directories.output_suffix, '.bak')

    def test_load_config_missing_file(self):
        """Test handling of missing configuration file."""
        # Test with non-existent file
        with self.assertRaises(FileNotFoundError):
            Config.load_from_file('/nonexistent/config.yaml')

    def test_load_config_with_kwargs(self):
        """Test loading configuration with keyword arguments."""
        # Override some config values
        override_config = {
            'binary': {
                'path': '/usr/bin/rsync',
                'flags': ['-av', '{input_file}', '{output_file}']
            },
            'directories': {
                'input_dir': '/data/input',
                'output_dir': '/data/output',
                'output_suffix': '.new'
            }
        }

        config = Config(**override_config)
        self.assertEqual(config.binary.path, '/usr/bin/rsync')
        self.assertEqual(config.binary.flags,
                         ['-av', '{input_file}', '{output_file}'])
        self.assertEqual(config.directories.input_dir, '/data/input')
        self.assertEqual(config.directories.output_dir, '/data/output')
        self.assertEqual(config.directories.output_suffix, '.new')

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            os.system(f"rm -rf {self.temp_dir}")
