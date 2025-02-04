"""Unit tests for resource monitor module."""

from datetime import datetime, timedelta
import unittest
from unittest.mock import MagicMock, patch

from orchestrator.resource_monitor import ProcessInfo, ResourceMonitor


class TestResourceMonitor(unittest.TestCase):
    """Test cases for ResourceMonitor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'disk_percent': 90.0,
            'max_processes': 2
        }
        self.monitor = ResourceMonitor(
            thresholds=self.thresholds,
            monitoring_interval=1,  # 1 second for testing
            throttle_threshold=0.9,
            recovery_threshold=0.7
        )

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

    @patch('psutil.Process')
    def test_add_and_remove_process(self, mock_process_class):
        """Test adding and removing processes from monitoring."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.memory_info.return_value = MagicMock(rss=1024 * 1024)
        mock_process.cpu_percent.return_value = 10.0
        mock_process_class.return_value = mock_process

        # Test adding process
        self.monitor.add_process('test_file.txt', mock_process)
        self.assertIn('test_file.txt', self.monitor.running_processes)
        proc_info = self.monitor.running_processes['test_file.txt']
        self.assertEqual(proc_info.pid, 12345)
        self.assertEqual(proc_info.memory_usage, 1024 * 1024)
        self.assertEqual(proc_info.cpu_usage, 10.0)

        # Test removing process
        self.monitor.remove_process('test_file.txt')
        self.assertNotIn('test_file.txt', self.monitor.running_processes)

    @patch('orchestrator.resource_monitor.ResourceMonitor.get_system_metrics')
    def test_throttling_activation(self, mock_metrics):
        """Test that throttling activates when resources are high."""
        # Setup initial state
        self.assertFalse(self.monitor.throttled)
        self.assertEqual(self.monitor.thresholds['max_processes'], 2)

        # Simulate high resource usage
        mock_metrics.return_value = {
            'cpu_percent': 75.0,  # 93.75% of threshold (80.0)
            'memory_percent': 50.0,
            'disk_percent': 50.0
        }

        # Force an update
        self.monitor.last_check = datetime.now() - timedelta(seconds=2)
        self.monitor.update_process_metrics()

        # Verify throttling was activated
        self.assertTrue(self.monitor.throttled)
        self.assertLess(
            self.monitor.thresholds['max_processes'],
            self.monitor.original_max_processes
        )

    @patch('orchestrator.resource_monitor.ResourceMonitor.get_system_metrics')
    def test_throttling_recovery(self, mock_metrics):
        """Test that throttling is removed when resources return to normal."""
        # Setup initial throttled state
        self.monitor.throttled = True
        self.monitor.thresholds['max_processes'] = 1

        # Simulate low resource usage
        mock_metrics.return_value = {
            'cpu_percent': 40.0,  # 50% of threshold
            'memory_percent': 40.0,
            'disk_percent': 40.0
        }

        # Force an update
        self.monitor.last_check = datetime.now() - timedelta(seconds=2)
        self.monitor.update_process_metrics()

        # Verify throttling was removed
        self.assertFalse(self.monitor.throttled)
        self.assertEqual(
            self.monitor.thresholds['max_processes'],
            self.monitor.original_max_processes
        )

    @patch('orchestrator.resource_monitor.ResourceMonitor.get_system_metrics')
    def test_process_cleanup(self, mock_metrics):
        """Test that dead processes are cleaned up during metrics update."""
        # Setup mock process that will raise NoSuchProcess
        mock_metrics.return_value = {
            'cpu_percent': 50.0,
            'memory_percent': 50.0,
            'disk_percent': 50.0
        }

        # Add a "dead" process
        self.monitor.running_processes['dead_process.txt'] = ProcessInfo(
            pid=99999,  # Non-existent PID
            start_time=datetime.now(),
            memory_usage=1024,
            cpu_usage=10.0
        )

        # Force an update
        self.monitor.last_check = datetime.now() - timedelta(seconds=2)
        self.monitor.update_process_metrics()

        # Verify the dead process was cleaned up
        self.assertNotIn('dead_process.txt', self.monitor.running_processes)
