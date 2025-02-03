"""Unit tests for resource monitor module."""

import unittest
from unittest.mock import patch

from orchestrator.resource_monitor import ResourceMonitor


class TestResourceMonitor(unittest.TestCase):
    """Test cases for ResourceMonitor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'disk_percent': 90.0
        }
        self.monitor = ResourceMonitor(self.thresholds)

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_get_system_metrics(self, mock_disk, mock_memory, mock_cpu):
        """Test getting system metrics."""
        # Mock the system calls
        mock_cpu.return_value = 50.0
        mock_memory.return_value.percent = 60.0
        mock_disk.return_value.percent = 70.0

        metrics = self.monitor.get_system_metrics()

        self.assertEqual(metrics['cpu_percent'], 50.0)
        self.assertEqual(metrics['memory_percent'], 60.0)
        self.assertEqual(metrics['disk_percent'], 70.0)

    @patch('orchestrator.resource_monitor.ResourceMonitor.get_system_metrics')
    def test_can_start_new_process_under_threshold(self, mock_metrics):
        """Test capacity check when resources are under thresholds."""
        mock_metrics.return_value = {
            'cpu_percent': 50.0,
            'memory_percent': 50.0,
            'disk_percent': 50.0
        }

        self.assertTrue(self.monitor.can_start_new_process())

    @patch('orchestrator.resource_monitor.ResourceMonitor.get_system_metrics')
    def test_can_start_new_process_over_threshold(self, mock_metrics):
        """Test capacity check when resources are over thresholds."""
        mock_metrics.return_value = {
            'cpu_percent': 90.0,  # Over threshold
            'memory_percent': 50.0,
            'disk_percent': 50.0
        }

        self.assertFalse(self.monitor.can_start_new_process())
