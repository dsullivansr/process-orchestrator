"""Tests for configuration management."""

import tempfile
import unittest

import yaml

from orchestrator.config import Config


class TestConfig(unittest.TestCase):
    """Test cases for configuration management."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'binary': {
                'path': '/usr/bin/test',
                'flags': ['--input={input_file}', '--output={output_file}']
            },
            'directories': {
                'input_dir': '/tmp/input',
                'output_dir': '/tmp/output'
            }
        }

    def test_load_config_from_file(self):
        """Test loading configuration from a YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as f:
            yaml.dump(self.test_config, f)
            f.flush()

            config = Config(config_path=f.name)

            self.assertEqual(config.binary.path, '/usr/bin/test')
            self.assertEqual(len(config.binary.flags), 2)
            self.assertEqual(config.directories.input_dir, '/tmp/input')
            self.assertEqual(config.directories.output_dir, '/tmp/output')

    def test_load_config_with_kwargs(self):
        """Test loading configuration with keyword arguments."""
        binary_config = {'path': '/usr/bin/custom', 'flags': ['--custom-flag']}
        directory_config = {
            'input_dir': '/custom/input',
            'output_dir': '/custom/output'
        }

        config = Config(binary=binary_config, directories=directory_config)

        self.assertEqual(config.binary.path, '/usr/bin/custom')
        self.assertEqual(config.binary.flags, ['--custom-flag'])
        self.assertEqual(config.directories.input_dir, '/custom/input')
        self.assertEqual(config.directories.output_dir, '/custom/output')

    def test_load_config_missing_file(self):
        """Test loading configuration with non-existent file."""
        config = Config(config_path='/nonexistent/file.yaml')

        # Should use default values
        self.assertEqual(config.binary.path, '/usr/bin/test')
        self.assertEqual(config.binary.flags, [])
